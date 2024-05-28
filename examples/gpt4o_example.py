import asyncio
import os
import aiohttp
import aiofiles
import zipfile
from playwright.async_api import async_playwright


async def fetch_images(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)

        # 等待图片加载
        await page.wait_for_selector("img")

        # 获取所有图片的 src 属性
        img_elements = await page.query_selector_all("img")
        img_urls = [
            await img.get_attribute("src")
            for img in img_elements
            if await img.get_attribute("src")
        ]

        await browser.close()
        return img_urls


async def download_image(session, url, path):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                f = await aiofiles.open(path, mode="wb")
                await f.write(await response.read())
                await f.close()
    except Exception as e:
        print(f"Failed to download {url}: {e}")


async def download_images(img_urls, download_folder):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for idx, url in enumerate(img_urls):
            img_name = os.path.join(download_folder, f"image_{idx}.jpg")
            tasks.append(download_image(session, url, img_name))
        await asyncio.gather(*tasks)


def create_zip(download_folder, zip_path):
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for root, dirs, files in os.walk(download_folder):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, download_folder))


async def main(url, download_folder, zip_path):
    img_urls = await fetch_images(url)
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)
    await download_images(img_urls, download_folder)
    create_zip(download_folder, zip_path)
    print(f"Images downloaded and zipped at {zip_path}")


if __name__ == "__main__":
    # 淘宝页面示例
    # url = "https://vuejs.org"
    url = "https://filatz.tmall.com"
    download_folder = "downloaded_images"
    zip_path = "images.zip"
    # 异步运行主函数
    asyncio.run(main(url, download_folder, zip_path))
