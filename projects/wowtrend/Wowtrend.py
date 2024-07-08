import re
import json
from collections import defaultdict
from playwright.sync_api import Playwright, sync_playwright, expect

def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    # 访问目标页面并点击登录
    page.goto("https://www.wow-trend.com/column/?nav_id=16&gender_id=72105")
    page.get_by_text("登录/注册").click()

    # 填写登录表单并提交
    page.get_by_placeholder("手机号/帐号").click()
    page.get_by_placeholder("手机号/帐号").fill("15700123731")
    page.get_by_placeholder("密码").fill("lemon.030613")
    page.get_by_role("button", name="登录").click()

    # 等待登录完成
    page.wait_for_timeout(5000)  # 等待5秒

    # 跳转到第58页
    page.get_by_placeholder("输入页码").click()
    page.get_by_placeholder("输入页码").fill("58")
    page.get_by_text("跳转").click()
    page.wait_for_load_state('networkidle')

    data = defaultdict(lambda: defaultdict(list))

    while True:
        # 模拟滚动，确保加载所有内容
        page.mouse.wheel(0, 10000)
        page.wait_for_timeout(2000)  # 等待2秒以加载内容

        # 爬取数据
        articles = page.locator('li.cardLi_2_x99.galleryLi_qsRlt')
        count = articles.count()
        for i in range(count):
            article = articles.nth(i)
            title = article.locator('div.title_2aONf.oneLineText span').get_attribute('title')
            link_element = article.locator('a[target="_blank"]').first
            link = link_element.get_attribute('href')
            images = article.locator('div.cardImgBox_3SgmZ img').evaluate_all('elements => elements.map(e => e.srcset)')
            brands = article.locator('div.subTitle_1ovwG span.hoverline').all_text_contents()
            if brands:
                category, brand, location = brands[0].split(", ")
            else:
                category = "Unknown"
                brand = "Unknown"
                location = "Unknown"

            data[category][brand].append({
                'title': title,
                'link': f"https://www.wow-trend.com{link}",
                'images': images,
                'location': location
            })

        # 检查是否有下一页按钮并点击
        next_button = page.get_by_role("listitem", name="下一页").locator("a")
        if next_button.count() > 0 and next_button.is_visible():
            next_button.click()
            page.wait_for_load_state('networkidle')
        else:
            break

    # 保存数据到JSON文件
    with open('articles.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    # 保持浏览器打开，等待进一步操作
    input("Press Enter to close the browser...")

    # 关闭浏览器
    context.close()
    browser.close()

with sync_playwright() as playwright:
    run(playwright)
