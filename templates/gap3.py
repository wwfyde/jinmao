import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.gap.com/browse/product.do?pid=793202002&vid=1&searchText=coat#pdp-page-content")
    page.get_by_label("close email sign up modal").click()
    page.get_by_role("button", name="product details").click()
    page.get_by_role("button", name="product details").click()
    page.get_by_role("button", name="product details").click()
    page.get_by_role("button", name="product details").click()
    page.get_by_role("button", name="product details").click()
    page.get_by_role("button", name="product details").press("Meta+Shift+c")
    page.get_by_role("button", name="fabric & care").click()
    page.get_by_role("button", name="fabric & care").press("Meta+Shift+c")
    page.get_by_text("% Wool, 40% Polyester, 10% Other").click()
    page.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
