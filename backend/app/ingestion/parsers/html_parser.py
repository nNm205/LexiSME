import re 
from pathlib import Path 
from datetime import datetime
from bs4 import BeautifulSoup
from app.core.logging import get_logger
from app.ingestion.parsers.base import BaseParser
from app.models.raw_document import RawDocument
from app.models.legal_document import LegalDocument
from app.models.metadata import DocumentMetadata

# =========================================================================
# LOGGING
# =========================================================================

logger = get_logger(__name__)

# =========================================================================
# CONSTANTS
# =========================================================================

METADATA_FIELDS_MAP = {
    "số hiệu": "so_hieu",
    "tên văn bản": "ten_van_ban",
    "loại văn bản": "loai_van_ban",
    "ngày ban hành": "ngay_ban_hanh",
    "ngày có hiệu lực": "hieu_luc_tu",
    "ngày hết hiệu lực": "hieu_luc_den",
    "tình trạng hiệu lực": "trang_thai_hieu_luc",
    "cơ quan ban hành": "co_quan_ban_hanh",
    "ngành": "bo_nganh",
}

TAC_DONG = {
    "Văn bản hướng dẫn áp dụng",
    "Văn bản quy định chi tiết, hướng dẫn thi hành",
    "Văn bản hợp nhất",
    "Văn bản sửa đổi bổ sung",
    "Văn bản đính chính",
    "Văn bản thay thế",
    "Văn bản bãi bỏ",
    "Văn bản dẫn chiếu",
    "Văn bản áp dụng",
    "Văn bản giải thích",
    "Văn bản đình chỉ thi hành",
    "Văn bản tạm ngưng hiệu lực",
    "Văn bản công bố"
}

DUOC_TAC_DONG = {
    "Văn bản được hướng dẫn áp dụng", 
    "Văn bản được quy định chi tiết, hướng dẫn thi hành",
    "Văn bản được hợp nhất", 
    "Văn bản được sửa đổi bổ sung",
    "Văn bản được đính chính", 
    "Văn bản được thay thế",
    "Văn bản bị bãi bỏ",
    "Văn bản được dẫn chiếu",
    "Căn cứ ban hành",
    "Văn bản được giải thích",
    "Văn bản bị đình chỉ thi hành",
    "Văn bản bị tạm ngưng hiệu lực",
    "Văn bản được công bố",
}

BASE_DIR = Path(__file__).resolve().parents[3]
OUTPUT_DIR = BASE_DIR / "data/processed/json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# =========================================================================
# HELPERS
# =========================================================================

def save_legal_document(doc: LegalDocument):
    output_file = OUTPUT_DIR / f"{doc.metadata.document_id}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(doc.model_dump_json(indent=2))

    logger.info(f"Saved -> {output_file}")

def normalize_date(date_str: str) -> str | None:
    if not date_str:
        return None

    try:
        dt = datetime.strptime(date_str.strip(), "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None

# =========================================================================
# HTML PARSER
# =========================================================================

class HTMLParser(BaseParser):
    # =========================================================================
    # PARSE
    # =========================================================================

    def parse(self, raw: RawDocument) -> LegalDocument:
        soup = BeautifulSoup(raw.toan_van_html, "lxml")
        text = soup.get_text(separator="\n", strip=True)
        metadata = self._extract_metadata(raw.thuoc_tinh_html)
        tac_dong_count, duoc_tac_dong_count = self._extract_relation_counts(raw.luoc_do_html)
        title = self._extract_title(raw.toan_van_html)

        document_metadata = DocumentMetadata(
            document_id=raw.document_id,
            source_type=raw.source,
            url=raw.url,
            so_hieu=metadata.get("so_hieu"),
            ten_van_ban=title,
            loai_van_ban=metadata.get("loai_van_ban"),
            co_quan_ban_hanh=metadata.get("co_quan_ban_hanh"),
            ngay_ban_hanh=metadata.get("ngay_ban_hanh"),
            hieu_luc_tu=metadata.get("hieu_luc_tu"),
            hieu_luc_den=metadata.get("hieu_luc_den"),
            trang_thai_hieu_luc=metadata.get("trang_thai_hieu_luc"),
            bo_nganh=metadata.get("bo_nganh"),
            content_length=len(text),
            so_van_ban_tac_dong=tac_dong_count,
            so_van_ban_duoc_tac_dong=duoc_tac_dong_count
        )

        return LegalDocument(
            metadata=document_metadata,
            content=text,
            content_html=raw.toan_van_html,
            content_length=len(text),
        )

    # =========================================================================
    # EXTRACTIONS
    # =========================================================================
    def _extract_title(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "lxml")
        title = soup.find("h1", class_="lawDocumentHeader_title___34g0")

        if not title:
            logger.warning("Cannot find title")
            return None

        return title.get_text(strip=True)

    def _extract_metadata(self, html) -> dict:
        soup = BeautifulSoup(html, "lxml")
        metadata = {}
        containers = soup.find_all("div", class_="ant-descriptions-item-container")

        for c in containers:
            label = c.find("span", class_="ant-descriptions-item-label")
            content = c.find("span", class_="ant-descriptions-item-content")

            if not label or not content:
                continue
            
            label_text = label.get_text(strip=True).lower()

            key = METADATA_FIELDS_MAP.get(label_text)
            if not key:
                continue
            
            value = content.get_text(" ", strip=True)

            if key in {"ngay_ban_hanh", "hieu_luc_tu", "hieu_luc_den"}:
                value = normalize_date(value)

            metadata[key] = value

        logger.debug("Extracted %s metadata fields", len(metadata))
        return metadata
    
    def _extract_relation_counts(self, html: str) -> tuple[int, int]:
        soup = BeautifulSoup(html, "lxml")
        tac_dong_count = 0
        duoc_tac_dong_count = 0

        for span in soup.find_all("span"):
            text = span.get_text(" ", strip=True)

            match = re.match(r"(.+?)\s*\((\d+)\)", text)
            if not match:
                continue

            relation_name = match.group(1).strip()
            count = int(match.group(2))

            if relation_name in TAC_DONG: 
                tac_dong_count += count
            elif relation_name in DUOC_TAC_DONG: 
                duoc_tac_dong_count += count
        
        logger.debug("Relations: tac_dong=%s, duoc_tac_dong=%s", tac_dong_count, duoc_tac_dong_count)
        return tac_dong_count, duoc_tac_dong_count