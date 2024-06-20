__doc__ = """"
https://www.next.co.uk/shop/gender-women-productaffiliation-clothing
"""

import re

from playwright.async_api import async_playwright


async def run(playwright):
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page()
    women = "https://www.next.co.uk/shop/gender-women-productaffiliation-clothing"
    men = "https://www.next.co.uk/shop/gender-men-productaffiliation-clothing-0"
    boys = "https://www.next.co.uk/shop/gender-newbornboys-gender-newbornunisex-gender-olderboys-gender-youngerboys-productaffiliation-boysclothing-0"
    girls = "https://www.next.co.uk/shop/gender-newborngirls-gender-newbornunisex-gender-oldergirls-gender-youngergirls-productaffiliation-girlsclothing-0"
    await page.goto(girls)

    # 点击 "Category" 以渲染类别中的子类别
    # await page.locator("//main/div/div/div[2]/header/nav/div/div[2]/div/div[1]/button").click()
    await page.locator('[data-testid="plp-filter-label-button-category"]').click()

    # 等待类别内容加载
    await page.wait_for_selector('[data-testid="plp-filter-list-wrapper-category"]')

    # 获取类别和数量
    categories = await page.locator(
        "//main/div/div/div[2]/header/nav/div/div[2]/div/div[2]/div/div[2]/div"
    ).element_handles()
    categories_list = []
    # 遍历每个类别获取名称和数量
    for category in categories:
        category_name_element = await category.query_selector("//label/span[2]/span/span[1]")
        category_count_element = await category.query_selector("//label/span[2]/span/span[2]")
        # print(f"Category: {category_name}, Count: {category_count}")
        if category_name_element and category_count_element:
            category_name = await category_name_element.inner_text()
            category_count = await category_count_element.inner_text()
            match = re.search(r"\((\d+)\)", category_count)
            count = match.group(1) if match else 0
            name = category_name.replace(" ", "").replace("-", "").replace("&", "").lower()
            categories_list.append((name, count))
            print(f"Category: {category_name}, Count: {count}")
    print(categories_list)

    await browser.close()


async def main():
    async with async_playwright() as playwright:
        await run(playwright)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())