from __future__ import annotations
from playwright.sync_api import Page
from app.ingestion.searchers.filters import SearchFilter
from app.ingestion.searchers.pagination import Pagination
from app.ingestion.searchers.extractors import SearchExtractor

class VBPLSearcher:
    def __init__(self, page: Page):
        self.page = page
        self.filters = SearchFilter(page)
        self.pagination = Pagination(page)
        self.extractor = SearchExtractor(page)

    def _has_results(self) -> bool:
        try:
            items = self.page.locator(".DocumentCard_documentTitle__aE_F_")
            return items.count() > 0
        except Exception:
            return False

    # ----------------------------------------------------------
    # SETUP FILTERS
    # ----------------------------------------------------------
    def setup_filters(
        self,
        document_types: list[str] | None = None,
        effective_status: list[str] | None = None,
    ):
        self.filters.setup_filters(
            document_types=document_types,
            effective_status=effective_status,
        )

    # ----------------------------------------------------------
    # SEARCH KEYWORD
    # ----------------------------------------------------------
    def search_keyword(
        self,
        keyword: str,
        max_pages: int | None = None,
    ):
        self.filters.search_keyword(keyword)
        self.page.wait_for_timeout(2000)

        if not self._has_results():
            print(f"[SKIP] No results for keyword: {keyword}")
            return

        yield from self._paginate(max_pages)

    # ----------------------------------------------------------
    # INTERNAL PAGINATION
    # ----------------------------------------------------------
    def _paginate(self, max_pages: int | None = None):
        page_index = 1
        while True:
            try:
                total = self.extractor.count()
            except Exception:
                total = 0

            print(f"[Page {page_index}] {total} documents")

            if total == 0:
                break

            for i in range(total):
                yield page_index, i

            if max_pages and page_index >= max_pages:
                break

            if not self.pagination.goto_next_page():
                break

            page_index += 1

    # ----------------------------------------------------------
    # SEARCH
    # ----------------------------------------------------------
    def search(
        self,
        keyword: str,
        document_types: list[str] | None = None,
        effective_status: list[str] | None = None,
        max_pages: int | None = None,
    ):
        self.filters.search(
            keyword=keyword,
            document_types=document_types,
            effective_status=effective_status,
        )

        self.page.wait_for_timeout(2000)

        if not self._has_results():
            print(f"[SKIP] No results for keyword: {keyword}")
            return

        yield from self._paginate(max_pages)