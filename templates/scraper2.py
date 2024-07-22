import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://login2.scrape.center/login?next=/")
    page.locator("input[name=\"username\"]").click()
    page.locator("input[name=\"username\"]").fill("admin")
    page.locator("input[name=\"password\"]").click()
    page.locator("input[name=\"password\"]").fill("admin")
    page.goto("https://login2.scrape.center/")
    page.get_by_text("-07-26 上映").click()
    page.locator("div:nth-child(4)").first.click()
    page.get_by_text("中国内地、中国香港").click()
    page.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
