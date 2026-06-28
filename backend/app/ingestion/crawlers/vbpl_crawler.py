from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page, TimeoutError

from app.core.constants import SourceType
from app.core.logging import get_logger
from app.ingestion.searchers.extractors import SearchExtractor
from app.models.raw_document import RawDocument

# ==========================================================
# LOGGING
# ==========================================================

logger = get_logger(__name__)

# ==========================================================
# CONSTANTS
# ==========================================================

BASE_DIR = Path(__file__).resolve().parents[3]
OUTPUT_DIR = BASE_DIR / "data/raw/json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PAGE_TIMEOUT = 30_000

# ==========================================================
# HELPERS
# ==========================================================

def save_raw_document(doc: RawDocument):
    output_file = OUTPUT_DIR / f"{doc.document_id}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(doc.model_dump_json(indent=2))

    logger.info(f"Saved -> {output_file}")


def is_already_crawled(document_id: str) -> bool:
    """Kiểm tra tài liệu đã được crawl chưa (dựa vào file trên disk)."""
    return (OUTPUT_DIR / f"{document_id}.json").exists()


# ==========================================================
# CRAWLER
# ==========================================================

class VBPLCrawler:
    def __init__(self, search_page: Page):
        self.search_page = search_page
        self.extractor = SearchExtractor(search_page)

    # ------------------------------------------------------
    # PUBLIC
    # ------------------------------------------------------

    def crawl(self, page_number: int, item_index: int) -> RawDocument:
        logger.info(f"Crawling page={page_number}, item={item_index}")

        start = time.perf_counter()

        # =========================
        # OPEN DETAIL PAGE (POPUP)
        # =========================
        item = self.extractor.get(item_index)
        item.scroll_into_view_if_needed()

        with self.search_page.expect_popup() as popup:
            item.locator(".DocumentCard_documentTitle__aE_F_").click()

        detail_page = popup.value

        try:
            detail_page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
        except TimeoutError:
            logger.warning("Initial load timeout, continue anyway")

        base_url = detail_page.url
        document_id = self._extract_document_id(base_url)

        logger.info(f"Document: {document_id}")

        # =========================
        # CRAWL TABS
        # =========================
        raw_doc = RawDocument(
            document_id=document_id,
            source=SourceType.VBPL,
            url=base_url,
            crawled_at=datetime.now(),
            crawl_time_seconds=0.0,
            toan_van_html=self._safe_crawl_tab(detail_page, base_url, "toan-van"),
            thuoc_tinh_html=self._safe_crawl_tab(detail_page, base_url, "thuoc-tinh"),
            luoc_do_html=self._safe_crawl_tab(detail_page, base_url, "luoc-do"),
        )

        raw_doc.crawl_time_seconds = round(time.perf_counter() - start, 2)

        detail_page.close()

        logger.info(f"Finished {document_id} ({raw_doc.crawl_time_seconds}s)")

        return raw_doc

    # ------------------------------------------------------
    # SAFE WRAPPER
    # ------------------------------------------------------

    def _safe_crawl_tab(self, page: Page, base_url: str, tab: str) -> str:
        try:
            return self._crawl_tab(page, base_url, tab)
        except Exception:
            logger.exception(f"Failed tab={tab} url={base_url}")
            return ""

    # ------------------------------------------------------
    # CORE TAB CRAWLER (STABLE)
    # ------------------------------------------------------

    def _crawl_tab(self, page: Page, base_url: str, tab: str) -> str:
        logger.info(f"Crawling tab: {tab}")

        url = f"{base_url}?tabs={tab}"

        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)

        # =========================
        # WAIT BASIC UI RENDER
        # =========================
        self._wait_dom_ready(page)

        # =========================
        # SPECIAL CASE: TOAN VAN
        # =========================
        if tab == "toan-van":
            self._wait_toan_van_header(page)

        # =========================
        # FINAL STABILITY CHECK
        # =========================
        self._wait_dom_stable(page)

        return page.content()

    # ------------------------------------------------------
    # STABILITY HELPERS
    # ------------------------------------------------------

    def _wait_dom_ready(self, page: Page):
        try:
            page.wait_for_selector("body", timeout=5000)
        except TimeoutError:
            logger.debug("Body not ready")

    def _wait_toan_van_header(self, page: Page):
        try:
            page.wait_for_selector(
                "text=CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM",
                timeout=8000,
            )
        except TimeoutError:
            logger.debug("Header not found (safe skip)")

    def _wait_dom_stable(self, page: Page):
        last_size = 0

        for _ in range(5):
            try:
                html = page.content()
                size = len(html)

                if size == last_size and size > 5000:
                    return

                last_size = size
                page.wait_for_timeout(700)

            except Exception:
                return

    # ------------------------------------------------------
    # UTIL
    # ------------------------------------------------------

    @staticmethod
    def _extract_document_id(url: str) -> str:
        return url.rstrip("/").split("--")[-1]