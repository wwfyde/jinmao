from playwright.sync_api import Playwright, sync_playwright


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.gap.com/")
    page.get_by_label("close email sign up modal").click()
    page.get_by_test_id("ahref_Women").click()
    page.get_by_text("Tees", exact=True).click()
    page.goto(
        "https://www.gap.com/browse/category.do?cid=17076#pageId=0&department=136&mlink=5643,DP_VCN_2_W_SP246077_CTA"
    )
    page.get_by_role("link", name="Product alternate image").click()
    page.get_by_role("link", name="Next").click()
    page.get_by_text("More DetailChesttightlooseOverall sizesmallbigLength purchasedregularWhich size").click()
    page.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
