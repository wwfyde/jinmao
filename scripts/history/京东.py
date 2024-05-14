import re
from playwright.sync_api import Playwright, sync_playwright, expect
from lxml import etree
import pandas as pd
import requests
file_path = r'C:/中式连衣裙'
def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(
        "https://mall.jd.com/view_search-199900-61477-57338-0-0-0-0-1-1-60.html?keyword=%25E4%25B8%25AD%25E5%25BC%258F%25E8%25BF%259E%25E8%25A1%25A3%25E8%25A3%2599")
    page.wait_for_timeout(3000)
    page.get_by_text("快速验证").click()
    page.wait_for_timeout(3000)
    page.get_by_role("link", name="微信").click()
    page.wait_for_timeout(5000)
    # page.goto("https://mall.jd.com/view_search-199900-61477-57338-0-0-0-0-1-1-60.html?keyword=%25E4%25B8%25AD%25E5%25BC%258F%25E8%25BF%259E%25E8%25A1%25A3%25E8%25A3%2599")
    for i in range(2,13):
        with page.expect_popup() as page1_info:
            page.locator("li:nth-child({}) > .jItem > .jPic > a".format(i)).first.click()
        page1 = page1_info.value
        page1.wait_for_timeout(5000)

        for x in range(20):
            page1.mouse.wheel(0, 300)
            page1.wait_for_timeout(500)
        html = page1.content()
        # print(html)
        page.wait_for_timeout(5000)
        tree = etree.HTML(html)
        # print(tree)
        # li_list = tree.xpath('/html/body/div[9]/div[2]/div[1]/div[2]/div[1]/div[7]/div[1]/div/div[2]/div[10]/div[14]/img/@src')[0]

        # print(li_list)                      /html/body/div[4]/div[4]/div[3]/div[1]/div[5]/div[5]/div/div[7]/img
        #                                       /html/body/div[4]/div[4]/div[3]/div[1]/div[5]/div[5]/div/div[4]/img

        # for j in range(30):                      /html/body/div[9]/div[2]/div[1]/div[2]/div[1]/div[7]/div[1]/div/div[2]/div[7]/div[11]/img
        #     try:                                 /html/body/div[9]/div[2]/div[1]/div[2]/div[1]/div[7]/div[1]/div/div[2]/div[9]/div[16]/img
        #         li_list = 'https:' + tree.xpath('/html/body/div[9]/div[2]/div[1]/div[2]/div[1]/div[7]/div[1]/div/div[2]/div[10]/div[{}]/img/@src'.format(j))[0]
        #         print(li_list)                   /html/body/div[9]/div[2]/div[1]/div[2]/div[1]/div[7]/div[1]/div/div[2]/div[35]/img[17]
        #         r = requests.get(li_list)        /html/body/div[9]/div[2]/div[1]/div[2]/div[1]/div[7]/div[1]/div/div[2]/div[34]
        #         img_name1 = file_path + '/' + li_list.split('/')[-1]
        #         with open(img_name1, 'wb') as f:
        #             f.write(r.content)
        #             print('{}下载完成'.format(img_name1))
        #     except IndexError:
        #     # print("The list of elements is empty, and no index could be accessed.")
        #         continue
        #     except Exception as e:
        # # print(f"An error occurred: {e}")
        #         continue
        # page1.close()
    # page.close()
    #
    # # ---------------------
    # context.close()
    # browser.close()


with sync_playwright() as playwright:
    run(playwright)
