class Pagination:
    def __init__(self, page):
        self.page = page

    def _get_next_btn(self):
        try:
            return self.page.locator(".ant-pagination-next")
        except Exception:
            return None

    def has_next_page(self) -> bool:
        try:
            next_btn = self.page.locator(".ant-pagination-next")

            if next_btn.count() == 0:
                return False

            cls = next_btn.first.get_attribute("class") or ""
            return "disabled" not in cls

        except Exception:
            return False

    def goto_next_page_safe(self):
        try:
            next_btn = self.page.locator(".ant-pagination-next")

            if next_btn.count() == 0:
                return False

            if "disabled" in (next_btn.first.get_attribute("class") or ""):
                return False

            current = self.current_page()

            next_btn.first.click()

            # 🔥 safer wait (không dùng networkidle)
            self.page.wait_for_timeout(1500)

            self.page.wait_for_function(
                f"""
                () => {{
                    const el = document.querySelector('.ant-pagination-item-active');
                    return el && Number(el.innerText) === {current + 1};
                }}
                """,
                timeout=10000
            )

            return True

        except Exception:
            return False

    def goto_next_page(self):
        return self.goto_next_page_safe()

    def current_page(self) -> int:
        try:
            active = self.page.locator(".ant-pagination-item-active")
            if active.count() == 0:
                return 1
            return int(active.first.inner_text())
        except Exception:
            return 1