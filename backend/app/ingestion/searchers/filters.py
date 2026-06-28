import re
from playwright.sync_api import Page, TimeoutError


class SearchFilter:
    def __init__(self, page: Page):
        self.page = page

    def _reset_state(self):
        try:
            for _ in range(3):
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(200)
            self.page.mouse.click(10, 10)
            self.page.wait_for_timeout(500)
        except Exception:
            pass

    def open_advanced_search(self):
        self._reset_state()

        btn = self.page.locator(
            "button",
            has=self.page.locator("span:text('Tìm kiếm nâng cao')")
        )

        for _ in range(3):
            try:
                btn.wait_for(state="visible", timeout=8000)
                btn.click()
                break
            except TimeoutError:
                self.page.wait_for_timeout(1000)

        self.page.wait_for_timeout(1500)

    # =========================================================
    # CLOSE DROPDOWN (NEW)
    # =========================================================
    def _close_dropdown(self):
        self.page.keyboard.press("Escape")
        try:
            self.page.wait_for_selector(
                "div.ant-select-item-option-content",
                state="hidden",
                timeout=5000
            )
        except TimeoutError:
            self.page.mouse.click(10, 10)
            self.page.wait_for_timeout(500)

    # =========================================================
    # OPEN SELECT
    # =========================================================
    def _open_select(self, label: str):
        self._close_dropdown()
        self.page.wait_for_timeout(300)

        form_item = (
            self.page
            .locator(f'label[title="{label}"]')
            .locator("xpath=ancestor::*[contains(@class,'ant-form-item')]")
        )

        selector = form_item.locator(".ant-select-selector")
        selector.wait_for(state="visible", timeout=10000)
        selector.click()

        self.page.wait_for_selector(
            "div.ant-select-dropdown:not(.ant-select-dropdown-hidden)",
            timeout=10000
        )
        self.page.wait_for_timeout(300)

    # =========================================================
    # SELECT OPTIONS
    # =========================================================
    def _select_options(self, values: list[str]):
        EXACT_MATCH_VALUES = {"Luật", "Bộ luật", "Chỉ thị", "Pháp lệnh"}

        dropdown = self.page.locator(
            "div.ant-select-dropdown:not(.ant-select-dropdown-hidden)"
        ).last
        options = dropdown.locator("div.ant-select-item-option-content")

        for value in values:
            try:
                if value in EXACT_MATCH_VALUES:
                    pattern = re.compile(r"^\s*" + re.escape(value) + r"\s*$")
                    option = options.filter(has_text=pattern).first
                else:
                    option = options.filter(has_text=value).first

                option.wait_for(state="visible", timeout=8000)
                option.scroll_into_view_if_needed()
                option.click(timeout=5000)
                self.page.wait_for_timeout(200)

            except Exception as e:
                print(f"[WARN] Option not found: {value} — {e}")

        self._close_dropdown()

    # =========================================================
    # PUBLIC METHODS
    # =========================================================
    def select_document_types(self, document_types: list[str]):
        if not document_types:
            return
        self._open_select("Loại văn bản")
        self._select_options(document_types)

    def select_effective_status(self, statuses: list[str]):
        if not statuses:
            return
        self._open_select("Tình trạng hiệu lực")
        self._select_options(statuses)

    def clear_keyword(self):
        input_box = self.page.locator("#keyword")
        input_box.wait_for(state="visible", timeout=10000)
        input_box.click()
        input_box.fill("")
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Backspace")
        self.page.wait_for_timeout(200)

    def input_keyword(self, keyword: str):
        input_box = self.page.locator("#keyword")
        input_box.wait_for(state="visible", timeout=10000)
        input_box.click()
        input_box.fill(keyword)
        self.page.wait_for_timeout(300)

    def click_search(self):
        search_button = (
            self.page
            .locator("#keyword")
            .locator("xpath=ancestor::span[contains(@class,'ant-input-affix-wrapper')]")
            .locator("button")
            .filter(has=self.page.locator("span:text('Tìm kiếm')"))
        )
        search_button.wait_for(state="visible", timeout=10000)
        search_button.click()
        self.page.wait_for_timeout(2000)

    # =========================================================
    # CHECK ADVANCED SEARCH PANEL STATE
    # =========================================================
    def _is_advanced_search_open(self) -> bool:
        try:
            label = self.page.locator('label[title="Loại văn bản"]')
            return label.is_visible(timeout=1000)
        except Exception:
            return False

    def _ensure_advanced_search_open(self):
        if self._is_advanced_search_open():
            return

        btn = self.page.locator(
            "button",
            has=self.page.locator("span:text('Tìm kiếm nâng cao')")
        )

        for _ in range(3):
            try:
                btn.wait_for(state="visible", timeout=8000)
                btn.click()
                self.page.locator('label[title="Loại văn bản"]').wait_for(
                    state="visible", timeout=5000
                )
                break
            except TimeoutError:
                self.page.wait_for_timeout(1000)

        self.page.wait_for_timeout(500)

    # =========================================================
    # SETUP FILTERS
    # =========================================================
    def setup_filters(
        self,
        document_types: list[str] | None = None,
        effective_status: list[str] | None = None,
    ):
        self._reset_state()
        self._ensure_advanced_search_open()
        self.select_document_types(document_types or [])
        self.select_effective_status(effective_status or [])

    # =========================================================
    # SEARCH KEYWORD 
    # =========================================================
    def search_keyword(self, keyword: str):
        self._ensure_advanced_search_open()
        self._close_dropdown()
        self.clear_keyword()
        self.input_keyword(keyword)
        self.click_search()

    # =========================================================
    # SEARCH 
    # =========================================================
    def search(
        self,
        keyword: str,
        document_types: list[str] | None = None,
        effective_status: list[str] | None = None,
    ):
        self.setup_filters(document_types, effective_status)
        self.search_keyword(keyword)