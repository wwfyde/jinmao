import os
import re
from playwright.sync_api import Playwright, sync_playwright, expect
from lxml import etree
import pandas as pd
import requests
file_path = r'C:/唯品会2'
def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch()
    context = browser.new_context()
    for z in range(14,25):
        page = context.new_page()
        page.goto("https://category.vip.com/suggest.php?keyword=%E4%B8%AD%E5%BC%8F%E8%BF%9E%E8%A1%A3%E8%A3%99&ff=235%7C12%7C1%7C1&page={}".format(z))
        for x in range(30):
            page.mouse.wheel(0, 400)
            page.wait_for_timeout(500)
        for i in range(2,122):
            with page.expect_popup() as page1_info:
                page.locator("#J_searchCatList > div:nth-child({}) > a".format(i)).first.click()
            page1 = page1_info.value
            page1.wait_for_timeout(5000)

            html = page1.content()
            # print(html)
            tree = etree.HTML(html)
            img_name = tree.xpath('//*[@id="J_detail_info_mation"]/div/p[1]/@title')[0]
            img_name = img_name.replace('|', '')
            new_folder_name = img_name
            # Full path of the new folder
            new_folder_path = os.path.join(file_path, new_folder_name)
            # Create the new folder if it doesn't exist
            if not os.path.exists(new_folder_path):
                os.makedirs(new_folder_path)
            for j in range(2,10):
                try:
                    li_list = 'https:' + tree.xpath('//*[@id="J-mer-ImgReview"]/div[1]/div[{}]/a/@href'.format(j))[0]
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
            page1.close()


    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
