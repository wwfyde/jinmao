import asyncio

from playwright.async_api import async_playwright


async def fetch_category_links(page):
    await page.goto("https://www.target.com/")
    await page.wait_for_selector('a[href^="/c/"]')
    category_elements = await page.locator('a[href^="/c/"]').all()
    category_links = [await element.get_attribute("href") for element in category_elements]
    print(category_links)
    return category_links


async def fetch_product_links(page, category_link):
    await page.goto(f"https://www.target.com{category_link}")
    await page.wait_for_selector('a[data-test="product-title"]')
    product_elements = await page.query_selector_all('a[data-test="product-title"]')
    product_links = [await element.get_attribute("href") for element in product_elements]
    return product_links


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        category_links = await fetch_category_links(page)
        print(f"Found {len(category_links)} categories.")

        all_product_links = []
        for category_link in category_links:
            product_links = await fetch_product_links(page, category_link)
            all_product_links.extend(product_links)
            print(f"Category {category_link}: Found {len(product_links)} products.")

        await browser.close()

        print(f"Total products found: {len(all_product_links)}")
        for link in all_product_links:
            print(f"https://www.target.com{link}")


if __name__ == "__main__":
    asyncio.run(main())
