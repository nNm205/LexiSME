from pathlib import Path 
from playwright.sync_api import sync_playwright
from app.ingestion.searchers.vbpl_searcher import VBPLSearcher
from app.ingestion.crawlers.vbpl_crawler import VBPLCrawler, save_raw_document, is_already_crawled
from app.ingestion.parsers.html_parser import HTMLParser, save_legal_document

# ============================================================================
# CONSTANTS
# ============================================================================

URL = "https://vbpl.vn"

SME_KEYWORDS = [
    # "doanh nghiệp nhỏ và vừa",
    # "SME",
    # "hộ kinh doanh",
    # "doanh nghiệp siêu nhỏ",
    # "start-up",
]

TAX_FINANCE = [
    # "thuế thu nhập doanh nghiệp",
    # "thuế giá trị gia tăng",
    # "quản lý thuế",
    # "kê khai thuế",
    # "ưu đãi thuế",
    "miễn giảm thuế",
]

BUSINESS_OPERATIONS = [
    "đăng ký doanh nghiệp",
    "giấy phép kinh doanh",
    "điều lệ công ty",
    "vốn điều lệ",
    "thành lập công ty",
    "giải thể doanh nghiệp",
    "phá sản doanh nghiệp",
]

LABOR = [
    "hợp đồng lao động",
    "tiền lương",
    "bảo hiểm xã hội",
    "luật lao động",
    "người lao động",
]

ACCOUNTING = [
    "kế toán doanh nghiệp",
    "báo cáo tài chính",
    "chuẩn mực kế toán",
    "sổ sách kế toán",
]

POLICY = [
    "hỗ trợ doanh nghiệp nhỏ và vừa",
    "chính sách phát triển doanh nghiệp",
    "hỗ trợ khởi nghiệp",
    "quỹ hỗ trợ doanh nghiệp",
]

SEARCH_KEYWORDS = (
    SME_KEYWORDS +
    TAX_FINANCE +
    BUSINESS_OPERATIONS +
    LABOR +
    ACCOUNTING +
    POLICY
)

DOCUMENT_TYPES = [
    "Luật",
    "Nghị định",
    "Thông tư",
    "Quyết định",
    "Chỉ thị",
    "Nghị quyết",
    "Pháp lệnh",
    "Văn bản hợp nhất",
    "Bộ luật",
]

# ============================================================================
# MAIN
# ============================================================================

class VBPLPipeline:
    def __init__(self, page):
        self.searcher = VBPLSearcher(page)
        self.crawler = VBPLCrawler(page)
        self.parser = HTMLParser()
        # RAM cache cho session hiện tại (tránh crawl lại trong cùng 1 run)
        self._session_seen: set[str] = set()

    # ----------------------------------------------------------
    # SETUP FILTER — gọi 1 lần duy nhất sau khi page load xong
    # ----------------------------------------------------------
    def setup(self):
        self.searcher.setup_filters(
            document_types=DOCUMENT_TYPES,
            effective_status=["Còn hiệu lực", "Hết hiệu lực một phần"],
        )

    # ----------------------------------------------------------
    # RUN MỖI KEYWORD
    # ----------------------------------------------------------
    def run(self, keyword: str, max_pages: int | None = None):
        for page_number, item_index in self.searcher.search_keyword(
            keyword=keyword,
            max_pages=max_pages,
        ):
            print(f"\n==================== Page {page_number} - Item {item_index} ====================")

            # --- Lấy document_id TRƯỚC khi crawl để dedup sớm ---
            item = self.crawler.extractor.get(item_index)
            try:
                # document_id nằm trong href của link title
                link = item.locator(".DocumentCard_documentTitle__aE_F_")
                href = link.get_attribute("href") or ""
                doc_id_preview = href.rstrip("/").split("--")[-1] if "--" in href else ""
            except Exception:
                doc_id_preview = ""

            # Dedup: check RAM cache + disk
            if doc_id_preview:
                if doc_id_preview in self._session_seen:
                    print(f"[SKIP] Already seen this session: {doc_id_preview}")
                    continue
                if is_already_crawled(doc_id_preview):
                    print(f"[SKIP] Already on disk: {doc_id_preview}")
                    self._session_seen.add(doc_id_preview)
                    continue

            # --- Crawl ---
            raw_doc = self.crawler.crawl(page_number, item_index)
            doc_id = raw_doc.document_id

            # Dedup lần 2 (nếu không extract được href trước)
            if doc_id in self._session_seen:
                print(f"[SKIP] Duplicate (post-crawl): {doc_id}")
                continue
            if is_already_crawled(doc_id) and not doc_id_preview:
                print(f"[SKIP] Already on disk (post-crawl): {doc_id}")
                self._session_seen.add(doc_id)
                continue

            self._session_seen.add(doc_id)
            save_raw_document(raw_doc)

            legal_doc = self.parser.parse(raw_doc)
            save_legal_document(legal_doc)

            print(f"Parsed: {legal_doc.metadata.document_id}")
            yield legal_doc


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        context = browser.new_context(ignore_https_errors=True)

        page = context.new_page()
        page.goto(URL)

        pipeline = VBPLPipeline(page)

        # ✅ Setup filter 1 lần duy nhất
        pipeline.setup()

        try:
            for keyword in SEARCH_KEYWORDS:
                print("\n" + "=" * 80)
                print(f"SEARCH KEYWORD: {keyword}")
                print("=" * 80)

                # ✅ Chỉ đổi keyword, filter giữ nguyên
                for doc in pipeline.run(keyword=keyword, max_pages=2):
                    print("TITLE:", doc.metadata.ten_van_ban)
        finally:
            browser.close()


if __name__ == "__main__":
    main()