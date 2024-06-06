import time

from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://login2.scrape.center/login?next=/")
    page.locator('input[name="username"]').fill("admin")
    page.locator('input[name="password"]').fill("admin")
    log.info(page.url)
    # 点击登录
    page.locator(
        "#app > div:nth-child(2) > div > div > div > div > div > form > div:nth-child(4) > div > input"
    ).click()
    log.info(page.url)
    # 获取所有url链接
    page.wait_for_load_state("networkidle")
    elements = page.locator("a.name").element_handles()
    log.info(elements)
    url = []
    for eletemnt in elements:
        url.append(eletemnt.get_attribute("href"))
    log.info(url)
    main_url = "https://login2.scrape.center"
    for i in url:
        page = context.new_page()
        page.goto(main_url + i)

        time.sleep(3)
        page.close()
    return

    expect(page.locator("a").nth(2)).to_be_visible()
    expect(page.locator("a").filter(has_text="霸王别姬 - Farewell My Concubine")).to_be_visible()
    page.get_by_text(
        "影片借一出《霸王别姬》的京戏，牵扯出三个人之间一段随时代风云变幻的爱恨情仇。段小楼（张丰毅 饰）与程蝶衣（张国荣 饰）是一对打小一起长大的师兄弟，两人一个演生，"
    ).click()
    page.get_by_role("heading", name="剧情简介").click()
    page.get_by_text("-07-26 上映").click()
    page.get_by_text("中国内地、中国香港").click()
    page.get_by_text("分钟").click()
    page.get_by_role("button", name="购票选座").click()
    page.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
