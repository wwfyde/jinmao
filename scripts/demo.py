import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://vuejs.org/")
    page.goto("https://vuejs.org/guide/quick-start.html")
    page.get_by_label("Main Navigation").get_by_role("link", name="Quick Start").click()
    page.get_by_text("The recommended IDE setup is").click()
    page.get_by_text("If you skipped the").click()
    page.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
