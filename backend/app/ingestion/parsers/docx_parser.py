from __future__ import annotations
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from app.core.logging import get_logger
from app.ingestion.parsers.base import BaseParser
from app.models.raw_document import RawDocument
from app.models.legal_document import LegalDocument
from app.models.metadata import DocumentMetadata
from app.core.constants import SourceType

# =====================================================================
# CONSTANTS
# =====================================================================

BASE_DIR = Path(__file__).resolve().parents[3]
OUTPUT_DIR = BASE_DIR / "data/processed/json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

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
    "VĂN BẢN HỢP NHẤT":   "Văn Bản Hợp Nhất",
}

_SO_HIEU_LUAT = re.compile(
    r"(?:Bộ\s+[Ll]uật|[Ll]uật)\s+số\s*[:\s]\s*(\S+)",
    re.IGNORECASE,
)

_SO_HIEU_CHUNG = re.compile(
    r"^Số\s*[:\s]\s*(\S+)",
    re.IGNORECASE,
)

_SEPARATOR_RE = re.compile(r"^[_\-\s]+$")

# =====================================================================
# LOGGING
# =====================================================================

logger = get_logger(__name__)

# =====================================================================
# HELPERS
# =====================================================================

def _w(name: str) -> str:
    return f"{{{_W}}}{name}"

def _nws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def _collect_runs(p_el: ET.Element) -> list[str]:
    runs: list[str] = []
    for r in p_el.findall(_w("r")):
        parts = [t.text for t in r.findall(_w("t")) if t.text]
        if parts:
            runs.append("".join(parts))
    return runs

def _p_text(p_el: ET.Element) -> str:
    return "".join(t.text for t in p_el.findall(f".//{_w('t')}") if t.text).strip()

def _p_bold(p_el: ET.Element) -> bool:
    for r in p_el.findall(_w("r")):
        rPr = r.find(_w("rPr"))
        if rPr is not None and rPr.find(_w("b")) is not None:
            return True
    return False

def _p_italic(p_el: ET.Element) -> bool:
    for r in p_el.findall(_w("r")):
        rPr = r.find(_w("rPr"))
        if rPr is not None and rPr.find(_w("i")) is not None:
            return True
    return False

def _p_align(p_el: ET.Element) -> str | None:
    pPr = p_el.find(_w("pPr"))
    if pPr is None:
        return None
    jc = pPr.find(_w("jc"))
    return jc.get(_w("val")) if jc is not None else None

def _tbl_cells(tbl_el: ET.Element) -> list[list[str]]:
    result: list[list[str]] = []
    for tr in tbl_el.findall(_w("tr")):
        row: list[str] = []
        for tc in tr.findall(_w("tc")):
            words = [
                t.text
                for t in tc.findall(f".//{_w('t')}")
                if t.text and t.text.strip()
            ]
            row.append(" ".join(words))
        result.append(row)
    return result

# =====================================================================
# BLOCK
# =====================================================================

class _Block:
    __slots__ = ("kind", "text", "runs", "bold", "italic", "align", "cells")

    def __init__(
        self,
        kind: str,
        text: str,
        runs: list[str] | None = None,
        bold: bool = False,
        italic: bool = False,
        align: str | None = None,
        cells: list[list[str]] | None = None,
    ):
        self.kind   = kind
        self.text   = text
        self.runs   = runs or []
        self.bold   = bold
        self.italic = italic
        self.align  = align
        self.cells  = cells or []

    def __repr__(self) -> str:
        flags = ("B" if self.bold else "") + ("I" if self.italic else "")
        return f"<{self.kind}[{self.align}{flags}] {self.text[:60]!r}>"

# =====================================================================
# READ BLOCKS FROM DOCX
# =====================================================================

def _read_blocks(docx_path: str) -> list[_Block]:
    with zipfile.ZipFile(docx_path, "r") as z:
        xml_bytes = z.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    body = root.find(_w("body"))
    if body is None:
        return []

    blocks: list[_Block] = []

    for child in body:
        local = child.tag.split("}")[-1]

        if local == "p":
            text = _p_text(child)
            if not text or _SEPARATOR_RE.match(text):
                continue
            blocks.append(_Block(
                kind="p",
                text=text,
                runs=_collect_runs(child),
                bold=_p_bold(child),
                italic=_p_italic(child),
                align=_p_align(child),
            ))

        elif local == "tbl":
            cells = _tbl_cells(child)
            rows  = ["\t".join(row) for row in cells if any(c.strip() for c in row)]
            text  = "\n".join(rows)
            if text.strip():
                blocks.append(_Block(kind="table", text=text, cells=cells))

    return blocks

# =====================================================================
# METADATA HELPERS
# =====================================================================

def _is_header_table(block: _Block) -> bool:
    if block.kind != "table" or not block.cells:
        return False
    first_row  = block.cells[0]
    right_cell = first_row[1] if len(first_row) > 1 else ""
    return "Độc" in right_cell and "lập" in right_cell and "phúc" in right_cell

def _extract_so_hieu(text: str) -> str | None:
    m = _SO_HIEU_LUAT.search(text)
    if m:
        return m.group(1).strip()
    m = _SO_HIEU_CHUNG.match(text.strip())
    if m:
        return m.group(1).strip()
    return None

def _extract_co_quan(left_cell: str) -> str | None:
    part = re.split(r"_{3,}", left_cell)[0].strip()
    part = _SO_HIEU_LUAT.split(part)[0].strip()
    part = _SO_HIEU_CHUNG.split(part)[0].strip()
    if not part:
        return None
    return part.title()

def _match_loai(text: str) -> str | None:
    upper = _nws(text).upper()
    for key in sorted(LOAI_VAN_BAN_MAP, key=len, reverse=True):
        if upper == key or upper.startswith(key + " ") or upper.startswith(key + ","):
            return LOAI_VAN_BAN_MAP[key]
    return None

def _extract_metadata_fields(
    blocks: list[_Block],
) -> tuple[str | None, str | None, str | None, str | None]:
    so_hieu = co_quan = loai_van_ban = ten_van_ban = None

    for block in blocks:
        if _is_header_table(block):
            first_row  = block.cells[0]
            left_cell  = first_row[0] if len(first_row) > 0 else ""
            so_hieu    = _extract_so_hieu(left_cell)
            co_quan    = _extract_co_quan(left_cell)
            break

    found_header = False
    ten_lines: list[str] = []

    for block in blocks:
        if not found_header:
            if _is_header_table(block):
                found_header = True
            continue

        if block.kind == "table":
            break

        text = block.text.strip()
        if not text:
            continue

        if re.match(r"^[Cc]ăn\s+cứ", text):
            break

        if not block.bold:
            if loai_van_ban and ten_lines:
                break
            continue

        if not loai_van_ban and block.runs:
            first_run = _nws(block.runs[0])
            matched   = _match_loai(first_run)
            if matched:
                loai_van_ban = matched
                rest = _nws(" ".join(block.runs[1:]))
                if rest:
                    ten_lines.append(rest)
                continue

        if not loai_van_ban:
            matched = _match_loai(text)
            if matched:
                loai_van_ban = matched
                continue

        if loai_van_ban:
            if _match_loai(text):
                break
            ten_lines.append(_nws(text))

    if ten_lines:
        raw = _nws(" ".join(ten_lines)).lower()
        ten = f"{loai_van_ban} {raw}" if raw else raw
        if so_hieu and so_hieu not in ten:
            ten = f"{ten} số {so_hieu}"
        ten_van_ban = ten

    return so_hieu, co_quan, loai_van_ban, ten_van_ban

def _build_content(blocks: list[_Block]) -> str:
    parts: list[str] = []
    for block in blocks:
        if block.kind == "table":
            parts.append(f"[TABLE]\n{block.text}\n[/TABLE]")
        else:
            parts.append(block.text)
    return "\n\n".join(parts)

def save_legal_document(doc: LegalDocument):
    output_file = OUTPUT_DIR / f"{doc.metadata.document_id}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(doc.model_dump_json(indent=2))

    logger.info(f"Saved -> {output_file}")

# =====================================================================
# PARSER
# =====================================================================

class DocxParser(BaseParser):
    def parse(self, raw: RawDocument) -> LegalDocument:
        blocks  = _read_blocks(raw.file_path)
        content = _build_content(blocks)
        metadata = self._build_metadata(raw, blocks, content)
        return LegalDocument(
            metadata=metadata,
            content=content,
            content_html=None,
            content_length=len(content),
        )

    def _build_metadata(
        self,
        raw: RawDocument,
        blocks: list[_Block],
        content: str,
    ) -> DocumentMetadata:
        so_hieu, co_quan, loai_van_ban, ten_van_ban = _extract_metadata_fields(blocks)
        return DocumentMetadata(
            document_id=raw.document_id,
            source_type=SourceType.DOCX,
            url=raw.url,
            so_hieu=so_hieu,
            ten_van_ban=ten_van_ban,
            loai_van_ban=loai_van_ban,
            co_quan_ban_hanh=co_quan,
            ngay_ban_hanh=None,
            trang_thai_hieu_luc=None,
            bo_nganh=None,
            content_length=len(content),
        )