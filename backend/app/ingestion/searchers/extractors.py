from __future__ import annotations
from playwright.sync_api import Page


class SearchExtractor:
    def __init__(self, page: Page):
        self.page = page

    def items(self):
        return self.page.locator("ul.ant-list-items > li")

    # =====================================================
    # SAFE COUNT (FIX RACE CONDITION)
    # =====================================================
    def count(self, timeout: int = 5000) -> int:
        try:
            # wait until at least DOM exists OR timeout
            self.page.wait_for_selector(
                "ul.ant-list-items",
                timeout=timeout
            )
        except Exception:
            return 0

        return self.items().count()

    def get(self, index: int):
        return self.items().nth(index)