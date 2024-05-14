import os
import re
from playwright.sync_api import Playwright, sync_playwright, expect
from lxml import etree
import requests

file_path = r'C:/gap_coat'
img_detail2 = []

def run(playwright: Playwright) -> None:
    global img_detail2
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.gap.com/browse/search.do?searchText=coat#department=Men")
    page.wait_for_timeout(10000)
    page.get_by_label("close email sign up modal").click()

    # for x in range(10):
    #     page.mouse.wheel(0, 400)
    #     page.wait_for_timeout(500)
    for i in range(1, 115):
        page.locator("#search-page > div > div > div > div.search-page__product-grid.css-1xlfwl6 > section > div > div:nth-child({})".format(i)).first.click()
        page.get_by_role("button", name="product details").click()

        # page.get_by_label("close email sign up modal").click()
        # page1.wait_for_timeout(5000)
        # for x in range(10):
        #     popup.mouse.wheel(0, 400)
        #     popup.wait_for_timeout(500)
        # page1.locator('//*[@id="buy-box-wrapper-id"]/div/div[2]/div/div/div/div[2]/div[2]/div/button').click()
        html = page.content()
        # print(html)
        tree = etree.HTML(html)
        # print(tree)
        img_name = tree.xpath('//*[@id="buy-box"]/div/h1/text()')[0]
        img_name = img_name.replace('|', '')
        img_name = img_name.replace('"', '')
        # print(img_name)
        price = tree.xpath('//*[@id="buy-box"]/div/div/div[1]/div[1]/span/text()')[0]
        # print(price)
        # print(img_name)
        color = tree.xpath('//*[@id="swatch-label--Color"]/span[2]/text()')[0]
        new_folder_name = img_name
        # Full path of the new folder
        new_folder_path = os.path.join(file_path, new_folder_name)
        # Create the new folder if it doesn't exist
        if not os.path.exists(new_folder_path):
            os.makedirs(new_folder_path)
        img_detail2.append(img_name)
        for j in range(1, 10):
            try:
                detail = tree.xpath('//*[@id="buy-box-wrapper-id"]/div/div[2]/div/div/div/div[2]/div[2]/div/div[1]/div/ul/li[{}]/span/text()'.format(j))[0]
                # print(detail)
                img_detail2.append(detail)
            except IndexError:
                # print("The list of elements is empty, and no index could be accessed.")
                continue
            except Exception as e:
                # print(f"An error occurred: {e}")
                continue
        img_detail2.append(price)
        img_detail2.append(color)
        img_detail3 = new_folder_path + '/' + img_name + '.txt'
        with open(img_detail3, 'w', encoding='utf-8') as f:
            for string in img_detail2:
                f.write(string + '\n')
        img_detail2 = []
        for j in range(1, 12):
            try:
                li_list = 'https://www.gap.com' + tree.xpath('//*[@id="product"]/div[1]/div[1]/div[3]/div[2]/div/div[{}]/div/a/@href'.format(j))[0]
                # print(li_list)
                img_name1 = new_folder_path + '/' + img_name + '{}.jpg'.format(j)
                r = requests.get(li_list)
                with open(img_name1, 'wb') as f:
                    f.write(r.content)
                    print('{}下载完成'.format(img_name1))

            except IndexError:
                # print("The list of elements is empty, and no index could be accessed.")
                continue
            except Exception as e:
                # print(f"An error occurred: {e}")
                continue
        page.goto("https://www.gap.com/browse/search.do?searchText=coat#department=Men")
        for x in range(10):
            page.mouse.wheel(0, 400)
            page.wait_for_timeout(500)
    # page.close()

    # ---------------------
    # context.close()
    # browser.close()


with sync_playwright() as playwright:
    run(playwright)
