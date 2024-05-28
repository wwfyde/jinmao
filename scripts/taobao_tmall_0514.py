import os
import random

import requests
from lxml import etree
from playwright.sync_api import Playwright, sync_playwright

file_path = "~/Projects/MoLook/Resources/Crawlers"

headers = {
    # "Cookie": "cna=G9q0HmxB5n8CAXxapaxDuVEj; thw=cn; miid=587659421084145203; t=61baaa00b18ef310857c0304d8bbb8db; _tb_token_=ee73e8e1e7571; xlly_s=1; _samesite_flag_=true; 3PcFlag=1715049915079; cookie2=1dcc33a4f2070b351b715f7d09fa8e9e; unb=2206510437106; lgc=tb780422052; cancelledSubSites=empty; cookie17=UUphzOff%2BfEYEvZVeQ%3D%3D; dnk=tb780422052; tracknick=tb780422052; _l_g_=Ug%3D%3D; sg=26a; _nk_=tb780422052; cookie1=UNRkgCrrUlSwf3I05o5zfKUsRnQDFsasqMcLXwB2iEE%3D; sgcookie=E100klUX7yUZJZWECqH2%2FZL2IIPi4%2FlVEwz8tvj4jqv4qVIVlNwdtwHTDWbBoS8EpaMrTtgq2AxQrJPY9gXzMCeEJFX3U1HAyk8Psm%2BotFlML%2BZ%2BBtEaU3YMzMld8rdPbO21; havana_lgc2_0=eyJoaWQiOjIyMDY1MTA0MzcxMDYsInNnIjoiOGU4Nzk2MWUzNTVjZWRlY2IwNmEyNWY2MzQ0NTJhY2IiLCJzaXRlIjowLCJ0b2tlbiI6IjFadF9pbnZYZUNoQTRHS2pab1FJcWZ3In0; _hvn_lgc_=0; havana_lgc_exp=1714236006798; cookie3_bak=1dcc33a4f2070b351b715f7d09fa8e9e; cookie3_bak_exp=1715309141390; wk_cookie2=1b16f6e549d57fdcc42651509bb93c31; wk_unb=UUphzOff%2BfEYEvZVeQ%3D%3D; uc3=lg2=WqG3DMC9VAQiUQ%3D%3D&id2=UUphzOff%2BfEYEvZVeQ%3D%3D&vt3=F8dD3exB0yz%2BOO2zuTM%3D&nk2=F5RCbbyMsDCw3Ws%3D; csg=b573e3a7; env_bak=FM%2BgywHD45XwpbBMXUlRhbnnGWOdMs7nFkhjFkxAb2pK; skt=dc938c96cf1c7d3a; existShop=MTcxNTA0OTk0MQ%3D%3D; uc4=id4=0%40U2grF8wSVF1w0zUbSpPKushVx55eFxiu&nk4=0%40FY4Jg5WwN8w7pFy4V6XxSYE%2FcS1bew%3D%3D; _cc_=W5iHLLyFfA%3D%3D; v=0; x=e%3D1%26p%3D*%26s%3D0%26c%3D0%26f%3D0%26g%3D0%26t%3D0; mt=ci=22_1; uc1=pas=0&cookie14=UoYfpCd%2FVL7sPQ%3D%3D&cookie16=U%2BGCWk%2F74Mx5tgzv3dWpnhjPaQ%3D%3D&cookie15=W5iHLLyFOGW7aA%3D%3D&cookie21=U%2BGCWk%2F7pY%2FF&existShop=false; mtop_partitioned_detect=1; _m_h5_tk=eec366bce67565bf8f4b567881a96b30_1715231643879; _m_h5_tk_enc=e2335cae7ff1bb8d84fed5b954d592f5; pnm_cku822=098%23E1hvf9vUvbZvUvCkvvvvvjinPL5UAj3vPLSh0jivPmPwgjl8PF5Z6jrUR2Fhtjr2iQhvCvvvpZptvpvhvvCvpUyCvvwCvhnm1W94uphvmvvvpwtrRfxDKphv8vvvphvvvvvvvvCj1QvvvaZvvhNjvvvmjvvvBGwvvvUUvvCj1Qvvv99EvpCW9fk6rCzUeiIL%2B3%2BuzjZ7%2Bu0OaAd6%2Ff8reEQaWXxreEAK5kx%2F1noKhq8rwZXl%2Bb8reE%2BaUPexdXkwdeQEfwoOd3wgnZ43Ib8reE%2BanvhCvvOvChCvvvvPvpvhvv2MMQ%3D%3D; isg=BMHBPzm3QyzyG68JeFCQZ6YQ0A3b7jXgWgMHvCMWukgnCuHcaz2isfcI7H5MAs0Y; tfstk=fSji_zVh-N8_AxhMFyx_YNTXDS4p1ftX1snvMnd48BRIXsK9DH-eFLoZ7ERNLwX5iCeb5hQHi65H_ce_5ERc1BCxDOIcRmX5hGe6DRt1Cnt4w7ERiO66cDRnAFFdL-JXwycXruB1Cvkig8QU2q2eph0M3s8w8HJJTdo23slEYB9X3f-2_JXeoFrxSB9nxLLa1I1bTlyvBFAPKziqmgnJSQWwtmPPxdVXaORn0mR6qInGKOFiV9K1l_vR6koGZTsCtp5zmWxfOZ52n6rSMh_R1gThdzoFphABzZ83QlWHjCYRxeMqShbV1iY1Sxw5Lh5CPQTaRW9hXgLDNecU_9BH_Ubc4cgEzIxScpyAYqgX7p9HwRuMn5tv0WRYKJ075FJBB7e3KqgX7p9HwJ2nPjTwddFR.",
    "Referer": "https://filatz.tmall.com//",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
}
selectors = [
    (
        "颜色分类",
        "#root > div > div.Item--main--1sEwqeT > div.Item--content--12o-RdR > div.BasicContent--root--1_NvQmc > div > div.BasicContent--itemInfo--2NdSOrj > div.BasicContent--sku--6N_nw6c > div > div > div:nth-child(1) > div:nth-child(1) > div > div.skuItem.current",
    ),
]


def run(playwright: Playwright) -> None:
    # 返回浏览器示例
    browser = playwright.chromium.launch(headless=False)

    context = browser.new_context()
    # 创建浏览器页面
    page = context.new_page()

    category_urls: list[tuple[str, str]] = [
        (
            "短袖上衣",
            "https://filatz.tmall.com/category-1579712545.htm?catId=1579712545&orderType=hotsell_desc",
        ),
        ("防晒衣", "https://filatz.tmall.com/category-1467365883.htm"),
        ("长袖T恤", "https://filatz.tmall.com/category-1608468515.htm"),
        ("卫衣", "https://filatz.tmall.com/category-1467365882.htm"),
        ("外套", "https://filatz.tmall.com/category-1548063239.htm"),
        ("POLO衫", "https://filatz.tmall.com/category-1587910298.htm"),
        ("羽绒服-棉服", "https://filatz.tmall.com/category-1610796766.htm"),
    ]
    sub_page = "https://detail.tmall.com/item.htm?abbucket=15&id=743714999126&rn=b26c43a48c0f3b94e3b134bdd3c6d128&sku_properties=1627207:2374355994"
    # 进入页面
    # 按页操作
    for name, c_url in category_urls:
        page.goto(c_url)
        page.wait_for_timeout(10 * 1000)  # for debug
        # 按销量排序, 并逐一点击商品, 共15行4列
        for line in range(1, 16):
            for col in range(1, 5):
                ...
                "#J_ShopSearchResult > div > div.J_TItems > div:nth-child(1) > dl:nth-child(1)"
                # 新窗口打开页面
                with page.expect_popup() as new_page_info:
                    page.locator(
                        f"#J_ShopSearchResult > div > div.J_TItems > div:nth-child({line}) > dl:nth-child({col})"
                    ).first.click()

                # 获取新的页面对象
                new_page = new_page_info.value
                new_page.wait_for_timeout(random.randrange(4000, 6000, 100))
                # 等待新页面加载完成, 或根据需要调整等待条件
                # new_page.wait_for_load_state('load')
                # 模拟页面滚动
                for x in range(20):
                    # 模拟页面滚动
                    new_page.mouse.wheel(0, random.randrange(2000, 3000, 100))
                    # 短暂停留
                    new_page.wait_for_timeout(500)

                # 获取整个页面对象
                html = new_page.content()

                # 使用tree选择器, 解析html文档
                tree = etree.HTML(html)

                # 获取图像链接
                img_name = tree.x
                pass
    pass
    return
    page.goto("https://filatz.tmall.com/category-1579712545.htm")
    # page.goto("https://login.taobao.com/member/login.jhtml?redirectURL=https%3a%2f%2fsalomon.tmall.com:443/category-1641148105.htm%2F_____tmd_____%2Fpage%2Flogin_jump%3Frand%3DS3WxGHAgAt756EpznwfNzJq2AFA2qBNla3j6EINUS8We9dazM_iKElp8DwVSHZUevpC41Bx7RzivXIj9RnZgdg%26_lgt_%3De1f50b3ed96081a28265d5a2d385a78e___247640___4cd74ece1af6c2290d81acc3ce7bf844___eaebc79cac1eb5d2f7d8b4595e00ec73344a42d5a0b8cf56539c823cd24ac06c4d21058431ad70e45dea6b2fa0159a4cf0c8ecb0c61290b7ed95ee13ac101dfdd50678d9b2c0796ff9fccd6b8938022839e3d62290f053dd9880b992b38644b6422bde2705f7c31a286568078ea2a284cb275547891fb7514c3fb8ed126375a0292678d7c5c665dc53b4cde39d4c4dd59b27ba30a9214a0f6a492577a290245dc33f5490355c6854f0f3e5df9d6d3e3a533bd8fa6a8892ee23b347e776e121201bd0a1810ac1d9df15ba0e82a854c17dc7803a869c837a66d9dfe2f3898ac072905f09905599cc6da857ee5959fa2be2c86215672b4bed54f4d7bc9245a9e2400767644733f4bb555d1c48f22a45f334b4a9e24b8aaf9f5c5f272e12a0d17f298d0d2c5da2bfc0f3cebad88e0fae64114de603b43929f1e19c0732370e8abe99d815335da42d7fb161fd014b686b43d4&uuid=e1f50b3ed96081a28265d5a2d385a78e")
    page.wait_for_timeout(10000)
    # page.get_by_role("button", name="保持", exact=True).click()

    #
    for y in range(4, 10):
        page.goto(
            "https://zhaoyandaxi.taobao.com/search.htm?spm=a1z10.3-c-s.w4002-14439897287.31.526e4715GZRexS&_ksTS=1715238222522_170&callback=jsonp171&input_charset=gbk&mid=w"
            "-14439897287-0&wid=14439897287&path=%2Fsearch.htm&search=y&orderType=hotsell_desc&viewType=grid&keyword=%B9%FA%B7%E7&pageNo={}#anchor".format()
        )
        # page.goto("https://login.taobao.com/member/login.jhtml?redirectURL=https%3a%2f%2fsalomon.tmall.com:443/category-1641148105.htm%2F_____tmd_____%2Fpage%2Flogin_jump%3Frand%3DS3WxGHAgAt756EpznwfNzJq2AFA2qBNla3j6EINUS8We9dazM_iKElp8DwVSHZUevpC41Bx7RzivXIj9RnZgdg%26_lgt_%3De1f50b3ed96081a28265d5a2d385a78e___247640___4cd74ece1af6c2290d81acc3ce7bf844___eaebc79cac1eb5d2f7d8b4595e00ec73344a42d5a0b8cf56539c823cd24ac06c4d21058431ad70e45dea6b2fa0159a4cf0c8ecb0c61290b7ed95ee13ac101dfdd50678d9b2c0796ff9fccd6b8938022839e3d62290f053dd9880b992b38644b6422bde2705f7c31a286568078ea2a284cb275547891fb7514c3fb8ed126375a0292678d7c5c665dc53b4cde39d4c4dd59b27ba30a9214a0f6a492577a290245dc33f5490355c6854f0f3e5df9d6d3e3a533bd8fa6a8892ee23b347e776e121201bd0a1810ac1d9df15ba0e82a854c17dc7803a869c837a66d9dfe2f3898ac072905f09905599cc6da857ee5959fa2be2c86215672b4bed54f4d7bc9245a9e2400767644733f4bb555d1c48f22a45f334b4a9e24b8aaf9f5c5f272e12a0d17f298d0d2c5da2bfc0f3cebad88e0fae64114de603b43929f1e19c0732370e8abe99d815335da42d7fb161fd014b686b43d4&uuid=e1f50b3ed96081a28265d5a2d385a78e")
        for i in range(2, 11):
            for j in range(1, 5):
                # 新窗口页面
                with page.expect_popup() as page1_info:
                    # 通过选择器点击项目连接
                    "#J_ShopSearchResult > div > div.J_TItems > div:nth-child(15) > dl.item.last > dt"
                    page.locator(
                        "#J_ShopSearchResult > div > div.shop-hesper-bd.grid > div:nth-child({}) > dl:nth-child({}) > dt".format(
                            i, j
                        )
                    ).first.click()
                page1 = page1_info.value
                # Waits for a random time between 4 to 6 seconds.
                page1.wait_for_timeout(random.randrange(4000, 6000, 1))
                for x in range(5):
                    #  Scrolls the popup page
                    page1.mouse.wheel(0, (random.randrange(500, 700, 10)))
                    page1.wait_for_timeout(500)
                # Gets the HTML content of the popup pag
                html = page1.content()
                print(html)
                tree = etree.HTML(html)
                img_name = tree.xpath(
                    '//*[@id="J_ShopSearchResult"]/div/div[3]/div[15]/dl[4]/dt'
                    '//*[@id="root"]/div/div[2]/div[2]/div[1]/div/div[2]/div[1]/h1/text()'
                )[0]

                img_name1 = img_name.replace(":", "")
                img_name3 = img_name1.replace(".", "")
                img_name3 = img_name3.replace("|", "")
                img_name3 = img_name3.replace('"', "")

                # amount = tree.xpath('//*[@id="root"]/div/div[2]/div[2]/div[1]/div/div[2]/div[1]/div/span/text()')[0]
                # print(amount)
                # img_name = page.locator("#J_ShopSearchResult > div > div.shop-hesper-bd.grid > div:nth-child({}) > dl:nth-child({}) > dd > a".format(i, j)).inner_text()

                # if int(amount.split(' ')[-1].replace('+', '')) >= 100:
                #     img_name = img_name + ' ' + amount
                # print(img_name)
                new_folder_name = img_name3
                # Full path of the new folder
                new_folder_path = os.path.join(file_path, new_folder_name)
                # Create the new folder if it doesn't exist
                if not os.path.exists(new_folder_path):
                    os.makedirs(new_folder_path)
                for x in range(1, 7):
                    try:
                        img_url = tree.xpath(
                            "/html/body/div[3]/div/div[2]/div[2]/div[1]/div/div[1]/div/ul/li[{}]/img/@src".format(
                                x
                            )
                        )[0]
                        # img_url = tree.xpath(
                        #         '//*[@id="root"]/div/div[2]/div[2]/div/div[1]/div[1]/div/div/img/@src')[0]
                        # print(img_url)
                        img_url = "https:" + img_url[:-23]
                        # print(img_url)
                        img_name2 = (
                            new_folder_path + "/" + img_name3 + "{}.jpg".format(x)
                        )
                        # img_name1 = new_folder_path + '/' + img_name + '.jpg'
                        # print(img_name1)
                        r = requests.get(url=img_url, headers=headers)
                        with open(img_name2, "wb") as f:
                            f.write(r.content)
                            print("{}下载完成".format(img_name2))

                    except IndexError:
                        # print("The list of elements is empty, and no index could be accessed.")
                        continue
                    except Exception:
                        # print(f"An error occurred: {e}")
                        continue
                page1.wait_for_timeout(random.randrange(1500, 2500, 1))
                page1.close()


if __name__ == "__main__":
    store_name = "FILA童装旗舰店"
    level_1_category = "男童"
    with sync_playwright() as playwright:
        run(playwright)
