import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.gap.com/")
    page.goto("https://www.gap.com/browse/product.do?pid=370407002&searchText=370407")
    page.goto("https://www.gap.com/browse/product.do?pid=370407002&searchText=370407#pdp-page-content")
    page.goto("https://www.gap.com/browse/GeneralNoResults.do?searchText=370407&requestedurl=www.gap.com%2Fbrowse%2Fproduct.do%3FsearchText%3D370407#pdp-page-content")
    page.goto("https://www.gap.com/browse/product.do?pid=370407002&searchText=370407#pdp-page-content")
    page.goto("https://www.gap.com/browse/product.do?pid=370407002&searchText=370407")
    page.goto("https://www.gap.com/")
    page.get_by_role("combobox", name="search").click()
    page.get_by_role("combobox", name="search").fill("370407")
    page.get_by_role("combobox", name="search").press("Enter")
    page.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
