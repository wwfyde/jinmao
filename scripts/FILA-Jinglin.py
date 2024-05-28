import os
import re
from playwright.sync_api import Playwright, sync_playwright, expect
from lxml import etree
import requests
import random
file_path = r'C:\爬虫图片\衣服\FILA\羽绒服'

headers = {
    'Cookie' : '_l_g_=Ug%3D%3D; login=true; cookie2=1dcc33a4f2070b351b715f7d09fa8e9e; cancelledSubSites=empty; sn=; _tb_token_=ee73e8e1e7571; wk_cookie2=1b16f6e549d57fdcc42651509bb93c31; t=61baaa00b18ef310857c0304d8bbb8db; cna=KNq0Hrc5hlACAXxapaxe7vQX; arms_uid=913cd9da-2ad6-4f27-8d21-2a74b356bbc6; tk_trace=oTRxOWSBNwn9dPyorMJE%2FoPdY8zMG1aAN%2F0TkjYGZjkj6rrK3kv4LgxGhtlxvv5CwTD%2BouWTjev%2BFfv7Xsw9yZeW1XCdLG2Ohf%2FufzHejzqrKibss0xEif%2BFvWQij9ilfZ4aRt6lTlfzDvhMkp9IV0CUMNWzBwJbV8Q8nAubwrTRUdHayEDx8CtuF9HYfHQp6nDuOGEh2iFnqORQ9QSJPWu7KhtM2Nr50JfxXsRqljbCl5qWJzTFEnTX4JwT0JFNGbF27s9fEsnf5KG5yt%2FU%2FYfKNV4i4nqpmRJyVWj8AvoPPYkTwrjg9JSWAexDu4FrVSr33VDvTYWbM%2FUSgqnwpDyNsjI%2B6%2BLXrfNs%2BncGXpI%2BPIDxZNNGLMwEb2%2BqC29KvOmbZwR4tW2w2lLjTxJIDh0BSMB8Y6GgIVt8IXztF8gsy2UdV9EeJ5Z9Up9kI1CBMcieqohBPetY9Sr3o89t1zRVpbrXQ6Ozo234k2o%2FGiugzG5v; miid=751852621154883030; dnk=henry_hoooo; tracknick=tb780422052; lid=tb780422052; unb=2206510437106; lgc=tb780422052; cookie1=UNRkgCrrUlSwf3I05o5zfKUsRnQDFsasqMcLXwB2iEE%3D; cookie17=UUphzOff%2BfEYEvZVeQ%3D%3D; _nk_=tb780422052; sg=26a; wk_unb=UUphzOff%2BfEYEvZVeQ%3D%3D; xlly_s=1; uc1=cookie14=UoYfpCBGAVdkYQ%3D%3D&cookie21=U%2BGCWk%2F7pY%2FF&existShop=false&cookie15=WqG3DMC9VAQiUQ%3D%3D&cookie16=V32FPkk%2FxXMk5UvIbNtImtMfJQ%3D%3D&pas=0; uc3=lg2=UIHiLt3xD8xYTw%3D%3D&vt3=F8dD3eMzh83XTuYjPT8%3D&nk2=F5RCbbyMsDCw3Ws%3D&id2=UUphzOff%2BfEYEvZVeQ%3D%3D; uc4=nk4=0%40FY4Jg5WwN8w7pFy4V6XxSYacmcW%2FtQ%3D%3D&id4=0%40U2grF8wSVF1w0zUbSpPKushVwPUiu%2FMT; sgcookie=E100pxyybwmX9ff5gJkhlJouvXX9oKL8Jwc0PdR%2Bh8lEXTFiDbOw0pGrlVPzk4YAdtchu1Ofv9wgjwlJdUvL8lFnnlrwQjbiRTe3EW0D7PY8OBc%3D; csg=0b7550bc; mtop_partitioned_detect=1; _m_h5_tk=7bfd6423d8243064b63e44f6b527f195_1715751135973; _m_h5_tk_enc=c8a0bcbdc9c114580b3fadd82fadc9fe; tfstk=fF1oNUqcnTJ72ruLqsA7gaezPNyYV0OBxMhpvBKU3n-f9TKLFW4HmNJ8PMIdnHjVm37Jvz1hng_weMbQPe-FYMxde-FOPaOBTld365QWD_VV6MvrUZlVleGE4YpRScRBTlEv8r5DsBsOOwuaqZzDJemEYMJE3q-XJY-FY3Jq0FY6THSeTrx2WeTrTpJeuK8-wvGej65fgPIBELVBx7sWrLxn9nhhq6h93h7ymXraYU9oka-mTX5chHKvP3yskHOJVa8lA5GWapX1JejuZbSh5ssDuGPn637fWOp5aJh9IQKkp_Ri877DZ3vNwLuK9G7c8OpcMPP6ZQ-PpQ_KSuQcZgQ5iw3E3QARndfk_5iyvtQGtefQASjG5ssDuGP34gPx3A-H1XT4JskIdL8XoharEeq5gOfEor4mC89ylUETorDIdL8XohU0oAiBUET8X; isg=BMfHIasQbRrPbun_YkdpCXQcVnuRzJuu8MHBapmzS9J1COLKopta_16KqshW4HMm',
    'Referer' : 'https://filatz.tmall.com/',
    'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
}
def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto(
        "https://filatz.tmall.com/category-1610796766.htm?spm=a1z10.5-b-s.w4010-22258296913.45.345a3267Suw06C&search=y&parentCatId=1256137555&parentCatName=%C4%D0%B4%F3%CD%AF%B7%FE%CA%CE%A3%A8120-170cm%A3%A9&catName=%D3%F0%C8%DE%B7%FE%2F%C3%DE%B7%FE#bd")
    # page.goto("https://login.taobao.com/member/login.jhtml?redirectURL=https%3a%2f%2fsalomon.tmall.com:443/category-1641148105.htm%2F_____tmd_____%2Fpage%2Flogin_jump%3Frand%3DS3WxGHAgAt756EpznwfNzJq2AFA2qBNla3j6EINUS8We9dazM_iKElp8DwVSHZUevpC41Bx7RzivXIj9RnZgdg%26_lgt_%3De1f50b3ed96081a28265d5a2d385a78e___247640___4cd74ece1af6c2290d81acc3ce7bf844___eaebc79cac1eb5d2f7d8b4595e00ec73344a42d5a0b8cf56539c823cd24ac06c4d21058431ad70e45dea6b2fa0159a4cf0c8ecb0c61290b7ed95ee13ac101dfdd50678d9b2c0796ff9fccd6b8938022839e3d62290f053dd9880b992b38644b6422bde2705f7c31a286568078ea2a284cb275547891fb7514c3fb8ed126375a0292678d7c5c665dc53b4cde39d4c4dd59b27ba30a9214a0f6a492577a290245dc33f5490355c6854f0f3e5df9d6d3e3a533bd8fa6a8892ee23b347e776e121201bd0a1810ac1d9df15ba0e82a854c17dc7803a869c837a66d9dfe2f3898ac072905f09905599cc6da857ee5959fa2be2c86215672b4bed54f4d7bc9245a9e2400767644733f4bb555d1c48f22a45f334b4a9e24b8aaf9f5c5f272e12a0d17f298d0d2c5da2bfc0f3cebad88e0fae64114de603b43929f1e19c0732370e8abe99d815335da42d7fb161fd014b686b43d4&uuid=e1f50b3ed96081a28265d5a2d385a78e")
    page.wait_for_timeout(10000)
    # page.get_by_role("button", name="保持", exact=True).click()
    # for num in range(1,3):
    #     page.goto(
    #         "https://filatz.tmall.com/category-1579712545.htm?spm=a1z10.5-b-s.w4011-22258296915.318.2dd3159dwYMHbE&catId=1579712545&pageNo={}#anchor".format(
    #             num))
        # page.goto("https://login.taobao.com/member/login.jhtml?redirectURL=https%3a%2f%2fsalomon.tmall.com:443/category-1641148105.htm%2F_____tmd_____%2Fpage%2Flogin_jump%3Frand%3DS3WxGHAgAt756EpznwfNzJq2AFA2qBNla3j6EINUS8We9dazM_iKElp8DwVSHZUevpC41Bx7RzivXIj9RnZgdg%26_lgt_%3De1f50b3ed96081a28265d5a2d385a78e___247640___4cd74ece1af6c2290d81acc3ce7bf844___eaebc79cac1eb5d2f7d8b4595e00ec73344a42d5a0b8cf56539c823cd24ac06c4d21058431ad70e45dea6b2fa0159a4cf0c8ecb0c61290b7ed95ee13ac101dfdd50678d9b2c0796ff9fccd6b8938022839e3d62290f053dd9880b992b38644b6422bde2705f7c31a286568078ea2a284cb275547891fb7514c3fb8ed126375a0292678d7c5c665dc53b4cde39d4c4dd59b27ba30a9214a0f6a492577a290245dc33f5490355c6854f0f3e5df9d6d3e3a533bd8fa6a8892ee23b347e776e121201bd0a1810ac1d9df15ba0e82a854c17dc7803a869c837a66d9dfe2f3898ac072905f09905599cc6da857ee5959fa2be2c86215672b4bed54f4d7bc9245a9e2400767644733f4bb555d1c48f22a45f334b4a9e24b8aaf9f5c5f272e12a0d17f298d0d2c5da2bfc0f3cebad88e0fae64114de603b43929f1e19c0732370e8abe99d815335da42d7fb161fd014b686b43d4&uuid=e1f50b3ed96081a28265d5a2d385a78e")
    for i in range(1, 16):
        for j in range(1, 5):
            with page.expect_popup() as page1_info:
                page.locator("#J_ShopSearchResult > div > div.J_TItems > div:nth-child({}) > dl:nth-child({}) > dt".format(i, j)).first.click()
            page1 = page1_info.value
            page1.wait_for_timeout(random.randrange(4000, 6000, 1))
            for x in range(20):
                page1.mouse.wheel(0, (random.randrange(2000, 3000, 100)))
                page1.wait_for_timeout(500)
            html = page1.content()
            # print(html)
            tree = etree.HTML(html)
            img_name = tree.xpath('//*[@id="root"]/div/div[2]/div[2]/div[1]/div/div[2]/div[1]/h1/text()')[0]

            img_name1 = img_name.replace(":", "")
            img_name3 = img_name1.replace(".", "")
            img_name3 = img_name3.replace("|", "")
            img_name3 = img_name3.replace('"', '')

            # amount = tree.xpath('//*[@id="root"]/div/div[2]/div[2]/div[1]/div/div[2]/div[1]/div/span/text()')[0]
            # print(amount)
            # img_name = page.locator("#J_ShopSearchResult > div > div.shop-hesper-bd.grid > div:nth-child({}) > dl:nth-child({}) > dd > a".format(i, j)).inner_text()

            # if int(amount.split(' ')[-1].replace('+', '')) >= 100:
            #     img_name = img_name + ' ' + amount
            # print(img_name)
            new_folder_name = img_name3 + '{}'.format(j)
            # Full path of the new folder
            new_folder_path = os.path.join(file_path, new_folder_name)
            # Create the new folder if it doesn't exist
            if not os.path.exists(new_folder_path):
                os.makedirs(new_folder_path)
            for x in range(1, 7):
                try:
                    img_url = tree.xpath(
                        '/html/body/div[3]/div/div[2]/div[2]/div[1]/div/div[1]/div/ul/li[{}]/img/@src'.format(x))[0]
                    # img_url = tree.xpath(
                    #         '//*[@id="root"]/div/div[2]/div[2]/div/div[1]/div[1]/div/div/img/@src')[0]
                    # print(img_url)
                    img_url = 'https:' + img_url[:-23]
                    # print(img_url)
                    img_name2 = new_folder_path + '/' + img_name3 + '{}.jpg'.format(x)
                    # img_name1 = new_folder_path + '/' + img_name + '.jpg'
                    # print(img_name1)
                    r = requests.get(url=img_url, headers=headers)
                    with open(img_name2, 'wb') as f:
                        f.write(r.content)
                        print('{}下载完成'.format(img_name2))

                except IndexError:
                    # print("The list of elements is empty, and no index could be accessed.")
                    continue
                except Exception as e:
                    # print(f"An error occurred: {e}")
                    continue
            for y in range(1, 26):
                try:
                    img_url = tree.xpath(
                        '//*[@id="root"]/div/div[2]/div[2]/div[1]/div/div[2]/div[5]/div/div/div[1]/div[1]/div/div[{}]/div/img/@src'.format(y))[0]
                    # img_url = tree.xpath(
                    #         '//*[@id="root"]/div/div[2]/div[2]/div/div[1]/div[1]/div/div/img/@src')[0]
                    # print(img_url)
                    img_url = 'https:' + img_url[:-19]
                    # print(img_url)
                    img_name2 = new_folder_path + '/' + img_url.split('/')[-1]
                    # img_name1 = new_folder_path + '/' + img_name + '.jpg'
                    # print(img_name1)
                    r = requests.get(url=img_url, headers=headers)
                    with open(img_name2, 'wb') as f:
                        f.write(r.content)
                        print('{}下载完成'.format(img_name2))

                except IndexError:
                    # print("The list of elements is empty, and no index could be accessed.")
                    continue
                except Exception as e:
                    # print(f"An error occurred: {e}")
                    continue
            for z in range(2, 33):
                try:
                    img_url = tree.xpath(
                        '//*[@id="root"]/div/div[2]/div[2]/div[2]/div[2]/div[1]/div/div[2]/div/div[{}]/img/@src'.format(
                            z))[0]
                    # print(img_url)
                    img_name2 = new_folder_path + '/' + img_url.split('/')[-1]
                    # img_name1 = new_folder_path + '/' + img_name + '.jpg'
                    # print(img_name1)
                    r = requests.get(url=img_url, headers=headers)
                    with open(img_name2, 'wb') as f:
                        f.write(r.content)
                        print('{}下载完成'.format(img_name2))

                except IndexError:
                    # print("The list of elements is empty, and no index could be accessed.")
                    continue
                except Exception as e:
                    # print(f"An error occurred: {e}")
                    continue
            page1.wait_for_timeout(random.randrange(1500, 2500, 1))
            page1.close()


with sync_playwright() as playwright:
    run(playwright)
