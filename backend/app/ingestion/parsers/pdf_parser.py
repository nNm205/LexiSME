import fitz
import os
import re
from app.ingestion.parsers.base import BaseParser
from app.models.raw_document import RawDocument
from app.models.legal_document import LegalDocument
from app.models.metadata import DocumentMetadata
from app.core.constants import SourceType

os.environ["FLAGS_use_mkldnn"] = "0"

# ===================================================================== 
# PATTERNS 
# =====================================================================

DOC_LAP_PATTERN = re.compile(
    r"Độc\s+lập\s*[-–]\s*Tự\s+do\s*[-–]\s*Hạnh\s+phúc"
)

SO_HIEU_LUAT_PATTERN = re.compile(
    r"(?:Bộ\s+[Ll]uật|[Ll]uật)\s+số\s*:\s*(\S+)",
    re.IGNORECASE,
)

SO_HIEU_CHUNG_PATTERN = re.compile(
    r"^Số\s*:\s*(\S+)",
    re.IGNORECASE,
)

CAN_CU_PATTERN = re.compile(r"^Căn\s+cứ", re.IGNORECASE)

DIA_DANH_PATTERN = re.compile(r".+,\s*ngày\s+\d+", re.IGNORECASE)

LOAI_VAN_BAN_MAP: dict[str, str] = {
    "BỘ LUẬT":             "Bộ Luật",
    "LUẬT":                "Luật",
    "NGHỊ ĐỊNH":           "Nghị Định",
    "THÔNG TƯ":            "Thông Tư",
    "QUYẾT ĐỊNH":          "Quyết Định",
    "NGHỊ QUYẾT":          "Nghị Quyết",
    "CHỈ THỊ":             "Chỉ Thị",
    "THÔNG TƯ LIÊN TỊCH": "Thông Tư Liên Tịch",
    "PHÁP LỆNH":           "Pháp Lệnh",
}

LOAI_CO_TEN_THUONG: set[str] = {
    "NGHỊ ĐỊNH", "QUYẾT ĐỊNH", "THÔNG TƯ",
    "NGHỊ QUYẾT", "CHỈ THỊ", "THÔNG TƯ LIÊN TỊCH",
}

SCANNED_CHAR_THRESHOLD = 100

# ===================================================================== 
# HELPERS
# =====================================================================

def _is_all_upper_vietnamese(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    
    has_alpha = any(ch.isalpha() for ch in stripped)
    if not has_alpha:
        return False
    return all(not ch.islower() for ch in stripped)

def _match_loai_van_ban(line: str) -> str | None:
    upper = line.strip().upper()
    for key in sorted(LOAI_VAN_BAN_MAP, key=len, reverse=True):
        if upper == key or upper.startswith(key):
            return LOAI_VAN_BAN_MAP[key]
    return None

def _is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if re.match(r'^[_\-\s]+$', stripped):
        return True
    if DIA_DANH_PATTERN.match(stripped):
        return True
    return False

# ===================================================================== 
# PARSER 
# =====================================================================

class PDFParser(BaseParser):
    _ocr_engine = None
    
    # ===================================================================== 
    # PARSE 
    # =====================================================================

    def parse(self, raw: RawDocument) -> LegalDocument:
        text = self._extract_text(raw.file_path)
        text = self._clean_text(text)
        metadata = self._extract_metadata(raw, text)
        return LegalDocument(
            metadata=metadata,
            content=text,
            content_html=None,
            content_length=len(text),
        )

    # ===================================================================== 
    # TEXT EXTRACTION
    # =====================================================================

    def _is_scanned(self, pdf_path: str) -> bool:
        doc = fitz.open(pdf_path)
        total_chars = sum(len(page.get_text()) for page in doc)
        doc.close()
        return total_chars < SCANNED_CHAR_THRESHOLD

    def _extract_text(self, pdf_path: str) -> str:
        if self._is_scanned(pdf_path):
            return self._extract_text_ocr(pdf_path)
        return self._extract_text_pymupdf(pdf_path)

    def _extract_text_pymupdf(self, pdf_path: str) -> str:
        doc = fitz.open(pdf_path)
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text

    def _extract_text_ocr(self, pdf_path: str) -> str:
        ocr = self._get_ocr_engine()
        doc = fitz.open(pdf_path)
        all_text: list[str] = []

        for page in doc:
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            results = ocr.readtext(img_bytes)
            page_lines = self._parse_ocr_result(results)
            if page_lines:
                all_text.append("\n".join(page_lines))

        doc.close()
        return "\n".join(all_text)

    def _parse_ocr_result(self, results) -> list[str]:
        lines: list[str] = []

        for (_, text, confidence) in results:
            text = text.strip()
            if text and confidence > 0.3:
                lines.append(text)

        return lines

    @classmethod
    def _get_ocr_engine(cls):
        if cls._ocr_engine is None:
            import easyocr 
            cls._ocr_engine = easyocr.Reader(["vi"], gpu=False)
        return cls._ocr_engine

    # ===================================================================== 
    # CLEAN TEXT 
    # =====================================================================

    def _clean_text(self, text: str) -> str:
        cleaned = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if re.match(r"^\d+$", line):
                continue
            cleaned.append(line)
        return "\n".join(cleaned)

    # ===================================================================== 
    # EXTRACT METADATA
    # =====================================================================

    def _extract_metadata(self, raw: RawDocument, text: str) -> DocumentMetadata:
        lines = text.split("\n")
        so_hieu, loai_van_ban, ten_van_ban = self._parse_header(lines)
        return DocumentMetadata(
            document_id=raw.document_id,
            source_type=SourceType.PDF,
            url=raw.url,
            so_hieu=so_hieu or None,
            ten_van_ban=ten_van_ban or None,
            loai_van_ban=loai_van_ban or None,
            co_quan_ban_hanh=None,
            ngay_ban_hanh=None,
            trang_thai_hieu_luc=None,
            bo_nganh=None,
            content_length=len(text),
        )

    # ===================================================================== 
    # HEADER PARSING
    # =====================================================================

    def _parse_header(
        self, lines: list[str]
    ) -> tuple[str | None, str | None, str | None]:
        doc_lap_idx = self._find_doc_lap_idx(lines)
        if doc_lap_idx is None:
            return None, None, None

        post_lines   = self._slice_post_header(lines, doc_lap_idx)
        so_hieu      = self._extract_so_hieu(post_lines)
        loai_van_ban = self._extract_loai_van_ban(post_lines)
        ten_van_ban  = self._extract_ten_van_ban(post_lines, loai_van_ban, so_hieu)

        return so_hieu, loai_van_ban, ten_van_ban

    def _find_doc_lap_idx(self, lines: list[str]) -> int | None:
        for i, line in enumerate(lines):
            if DOC_LAP_PATTERN.search(line):
                return i
        return None

    def _slice_post_header(self, lines: list[str], start: int) -> list[str]:
        result = []
        for line in lines[start + 1:]:
            if CAN_CU_PATTERN.match(line.strip()):
                break
            result.append(line.strip())
        return result

    def _extract_so_hieu(self, lines: list[str]) -> str | None:
        for line in lines:
            m = SO_HIEU_LUAT_PATTERN.search(line)
            if m:
                return m.group(1).strip()
            m = SO_HIEU_CHUNG_PATTERN.match(line.strip())
            if m:
                return m.group(1).strip()
        return None

    def _extract_loai_van_ban(self, post_lines: list[str]) -> str | None:
        for line in post_lines:
            stripped = line.strip()
            if _is_noise_line(stripped) or not stripped:
                continue
            if _is_all_upper_vietnamese(stripped):
                loai = _match_loai_van_ban(stripped)
                if loai:
                    return loai
        return None

    def _extract_ten_van_ban(
        self,
        post_lines: list[str],
        loai_van_ban: str | None,
        so_hieu: str | None,
    ) -> str | None:
        if not loai_van_ban:
            return None

        loai_upper = loai_van_ban.upper()
        is_thuong  = loai_upper in LOAI_CO_TEN_THUONG

        title_lines: list[str] = []
        collecting  = False

        for line in post_lines:
            stripped = line.strip()

            if not stripped or _is_noise_line(stripped):
                continue

            if not collecting:
                if _is_all_upper_vietnamese(stripped) and stripped.upper() == loai_upper:
                    collecting = True
                continue

            if is_thuong:
                if _is_all_upper_vietnamese(stripped):
                    break
                title_lines.append(stripped)
            else:
                if SO_HIEU_LUAT_PATTERN.search(stripped):
                    continue         
                if _is_all_upper_vietnamese(stripped):
                    title_lines.append(stripped)
                else:
                    break

        if not title_lines:
            return None

        ten_raw = " ".join(title_lines).lower()
        return f"{loai_van_ban} {ten_raw} số {so_hieu}" if so_hieu else ten_raw