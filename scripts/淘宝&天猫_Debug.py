import os
from playwright.sync_api import Playwright, sync_playwright
from lxml import etree
import requests
import random

file_path = r"C:\爬虫图片\衣服\赵大喜"

headers = {
    # 'Cookie' : 'cna=G9q0HmxB5n8CAXxapaxDuVEj; thw=cn; miid=587659421084145203; t=61baaa00b18ef310857c0304d8bbb8db; _tb_token_=ee73e8e1e7571; xlly_s=1; _samesite_flag_=true; 3PcFlag=1715049915079; cookie2=1dcc33a4f2070b351b715f7d09fa8e9e; unb=2206510437106; lgc=tb780422052; cancelledSubSites=empty; cookie17=UUphzOff%2BfEYEvZVeQ%3D%3D; dnk=tb780422052; tracknick=tb780422052; _l_g_=Ug%3D%3D; sg=26a; _nk_=tb780422052; cookie1=UNRkgCrrUlSwf3I05o5zfKUsRnQDFsasqMcLXwB2iEE%3D; sgcookie=E100klUX7yUZJZWECqH2%2FZL2IIPi4%2FlVEwz8tvj4jqv4qVIVlNwdtwHTDWbBoS8EpaMrTtgq2AxQrJPY9gXzMCeEJFX3U1HAyk8Psm%2BotFlML%2BZ%2BBtEaU3YMzMld8rdPbO21; havana_lgc2_0=eyJoaWQiOjIyMDY1MTA0MzcxMDYsInNnIjoiOGU4Nzk2MWUzNTVjZWRlY2IwNmEyNWY2MzQ0NTJhY2IiLCJzaXRlIjowLCJ0b2tlbiI6IjFadF9pbnZYZUNoQTRHS2pab1FJcWZ3In0; _hvn_lgc_=0; havana_lgc_exp=1714236006798; cookie3_bak=1dcc33a4f2070b351b715f7d09fa8e9e; cookie3_bak_exp=1715309141390; wk_cookie2=1b16f6e549d57fdcc42651509bb93c31; wk_unb=UUphzOff%2BfEYEvZVeQ%3D%3D; uc3=lg2=WqG3DMC9VAQiUQ%3D%3D&id2=UUphzOff%2BfEYEvZVeQ%3D%3D&vt3=F8dD3exB0yz%2BOO2zuTM%3D&nk2=F5RCbbyMsDCw3Ws%3D; csg=b573e3a7; env_bak=FM%2BgywHD45XwpbBMXUlRhbnnGWOdMs7nFkhjFkxAb2pK; skt=dc938c96cf1c7d3a; existShop=MTcxNTA0OTk0MQ%3D%3D; uc4=id4=0%40U2grF8wSVF1w0zUbSpPKushVx55eFxiu&nk4=0%40FY4Jg5WwN8w7pFy4V6XxSYE%2FcS1bew%3D%3D; _cc_=W5iHLLyFfA%3D%3D; v=0; x=e%3D1%26p%3D*%26s%3D0%26c%3D0%26f%3D0%26g%3D0%26t%3D0; mt=ci=22_1; uc1=pas=0&cookie14=UoYfpCd%2FVL7sPQ%3D%3D&cookie16=U%2BGCWk%2F74Mx5tgzv3dWpnhjPaQ%3D%3D&cookie15=W5iHLLyFOGW7aA%3D%3D&cookie21=U%2BGCWk%2F7pY%2FF&existShop=false; mtop_partitioned_detect=1; _m_h5_tk=eec366bce67565bf8f4b567881a96b30_1715231643879; _m_h5_tk_enc=e2335cae7ff1bb8d84fed5b954d592f5; pnm_cku822=098%23E1hvf9vUvbZvUvCkvvvvvjinPL5UAj3vPLSh0jivPmPwgjl8PF5Z6jrUR2Fhtjr2iQhvCvvvpZptvpvhvvCvpUyCvvwCvhnm1W94uphvmvvvpwtrRfxDKphv8vvvphvvvvvvvvCj1QvvvaZvvhNjvvvmjvvvBGwvvvUUvvCj1Qvvv99EvpCW9fk6rCzUeiIL%2B3%2BuzjZ7%2Bu0OaAd6%2Ff8reEQaWXxreEAK5kx%2F1noKhq8rwZXl%2Bb8reE%2BaUPexdXkwdeQEfwoOd3wgnZ43Ib8reE%2BanvhCvvOvChCvvvvPvpvhvv2MMQ%3D%3D; isg=BMHBPzm3QyzyG68JeFCQZ6YQ0A3b7jXgWgMHvCMWukgnCuHcaz2isfcI7H5MAs0Y; tfstk=fSji_zVh-N8_AxhMFyx_YNTXDS4p1ftX1snvMnd48BRIXsK9DH-eFLoZ7ERNLwX5iCeb5hQHi65H_ce_5ERc1BCxDOIcRmX5hGe6DRt1Cnt4w7ERiO66cDRnAFFdL-JXwycXruB1Cvkig8QU2q2eph0M3s8w8HJJTdo23slEYB9X3f-2_JXeoFrxSB9nxLLa1I1bTlyvBFAPKziqmgnJSQWwtmPPxdVXaORn0mR6qInGKOFiV9K1l_vR6koGZTsCtp5zmWxfOZ52n6rSMh_R1gThdzoFphABzZ83QlWHjCYRxeMqShbV1iY1Sxw5Lh5CPQTaRW9hXgLDNecU_9BH_Ubc4cgEzIxScpyAYqgX7p9HwRuMn5tv0WRYKJ075FJBB7e3KqgX7p9HwJ2nPjTwddFR.',
    "Referer": "https://shop114435230.taobao.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
}


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto(
        "https://zhaoyandaxi.taobao.com/search.htm?spm=a1z10.3-c-s.w4002-14439897287.31.526e4715GZRexS&_ksTS=1715238222522_170&callback=jsonp171&input_charset=gbk&mid=w-14439897287-0&wid=14439897287&path=%2Fsearch.htm&search=y&orderType=hotsell_desc&viewType=grid&keyword=%B9%FA%B7%E7&pageNo=1#anchor"
    )
    # page.goto("https://login.taobao.com/member/login.jhtml?redirectURL=https%3a%2f%2fsalomon.tmall.com:443/category-1641148105.htm%2F_____tmd_____%2Fpage%2Flogin_jump%3Frand%3DS3WxGHAgAt756EpznwfNzJq2AFA2qBNla3j6EINUS8We9dazM_iKElp8DwVSHZUevpC41Bx7RzivXIj9RnZgdg%26_lgt_%3De1f50b3ed96081a28265d5a2d385a78e___247640___4cd74ece1af6c2290d81acc3ce7bf844___eaebc79cac1eb5d2f7d8b4595e00ec73344a42d5a0b8cf56539c823cd24ac06c4d21058431ad70e45dea6b2fa0159a4cf0c8ecb0c61290b7ed95ee13ac101dfdd50678d9b2c0796ff9fccd6b8938022839e3d62290f053dd9880b992b38644b6422bde2705f7c31a286568078ea2a284cb275547891fb7514c3fb8ed126375a0292678d7c5c665dc53b4cde39d4c4dd59b27ba30a9214a0f6a492577a290245dc33f5490355c6854f0f3e5df9d6d3e3a533bd8fa6a8892ee23b347e776e121201bd0a1810ac1d9df15ba0e82a854c17dc7803a869c837a66d9dfe2f3898ac072905f09905599cc6da857ee5959fa2be2c86215672b4bed54f4d7bc9245a9e2400767644733f4bb555d1c48f22a45f334b4a9e24b8aaf9f5c5f272e12a0d17f298d0d2c5da2bfc0f3cebad88e0fae64114de603b43929f1e19c0732370e8abe99d815335da42d7fb161fd014b686b43d4&uuid=e1f50b3ed96081a28265d5a2d385a78e")
    page.wait_for_timeout(50000)
    # page.get_by_role("button", name="保持", exact=True).click()
    for y in range(4, 10):
        page.goto(
            "https://zhaoyandaxi.taobao.com/search.htm?spm=a1z10.3-c-s.w4002-14439897287.31"
            ".526e4715GZRexS&_ksTS=1715238222522_170&callback=jsonp171&input_charset=gbk&mid=w"
            "-14439897287-0&wid=14439897287&path=%2Fsearch.htm&search=y&orderType=hotsell_desc"
            "&viewType=grid&keyword=%B9%FA%B7%E7&pageNo={}#anchor".format(y)
        )
        # page.goto("https://login.taobao.com/member/login.jhtml?redirectURL=https%3a%2f%2fsalomon.tmall.com:443/category-1641148105.htm%2F_____tmd_____%2Fpage%2Flogin_jump%3Frand%3DS3WxGHAgAt756EpznwfNzJq2AFA2qBNla3j6EINUS8We9dazM_iKElp8DwVSHZUevpC41Bx7RzivXIj9RnZgdg%26_lgt_%3De1f50b3ed96081a28265d5a2d385a78e___247640___4cd74ece1af6c2290d81acc3ce7bf844___eaebc79cac1eb5d2f7d8b4595e00ec73344a42d5a0b8cf56539c823cd24ac06c4d21058431ad70e45dea6b2fa0159a4cf0c8ecb0c61290b7ed95ee13ac101dfdd50678d9b2c0796ff9fccd6b8938022839e3d62290f053dd9880b992b38644b6422bde2705f7c31a286568078ea2a284cb275547891fb7514c3fb8ed126375a0292678d7c5c665dc53b4cde39d4c4dd59b27ba30a9214a0f6a492577a290245dc33f5490355c6854f0f3e5df9d6d3e3a533bd8fa6a8892ee23b347e776e121201bd0a1810ac1d9df15ba0e82a854c17dc7803a869c837a66d9dfe2f3898ac072905f09905599cc6da857ee5959fa2be2c86215672b4bed54f4d7bc9245a9e2400767644733f4bb555d1c48f22a45f334b4a9e24b8aaf9f5c5f272e12a0d17f298d0d2c5da2bfc0f3cebad88e0fae64114de603b43929f1e19c0732370e8abe99d815335da42d7fb161fd014b686b43d4&uuid=e1f50b3ed96081a28265d5a2d385a78e")
        for i in range(2, 11):
            for j in range(1, 4):
                with page.expect_popup() as page1_info:
                    page.locator(
                        "#J_ShopSearchResult > div > div.shop-hesper-bd.grid > div:nth-child({}) > dl:nth-child({}) > dt".format(
                            i, j
                        )
                    ).first.click()
                page1 = page1_info.value
                page1.wait_for_timeout(random.randrange(4000, 6000, 1))
                for x in range(5):
                    page1.mouse.wheel(0, (random.randrange(500, 700, 10)))
                    page1.wait_for_timeout(500)
                html = page1.content()
                log.info(html)
                tree = etree.HTML(html)
                img_name = tree.xpath('//*[@id="root"]/div/div[2]/div[2]/div[1]/div/div[2]/div[1]/h1/text()')[0]

                img_name1 = img_name.replace(":", "")
                img_name3 = img_name1.replace(".", "")
                img_name3 = img_name3.replace("|", "")
                img_name3 = img_name3.replace('"', "")

                # amount = tree.xpath('//*[@id="root"]/div/div[2]/div[2]/div[1]/div/div[2]/div[1]/div/span/text()')[0]
                # log.info(amount)
                # img_name = page.locator("#J_ShopSearchResult > div > div.shop-hesper-bd.grid > div:nth-child({}) > dl:nth-child({}) > dd > a".format(i, j)).inner_text()

                # if int(amount.split(' ')[-1].replace('+', '')) >= 100:
                #     img_name = img_name + ' ' + amount
                # log.info(img_name)
                new_folder_name = img_name3
                # Full path of the new folder
                new_folder_path = os.path.join(file_path, new_folder_name)
                # Create the new folder if it doesn't exist
                if not os.path.exists(new_folder_path):
                    os.makedirs(new_folder_path)
                for x in range(1, 7):
                    try:
                        img_url = tree.xpath(
                            "/html/body/div[3]/div/div[2]/div[2]/div[1]/div/div[1]/div/ul/li[{}]/img/@src".format(x)
                        )[0]
                        # img_url = tree.xpath(
                        #         '//*[@id="root"]/div/div[2]/div[2]/div/div[1]/div[1]/div/div/img/@src')[0]
                        log.info(img_url)
                        img_url = "https:" + img_url[:-23]
                        log.info(img_url)
                        img_name2 = new_folder_path + "/" + img_name3 + "{}.jpg".format(x)
                        # img_name1 = new_folder_path + '/' + img_name + '.jpg'
                        # log.info(img_name1)
                        r = requests.get(url=img_url, headers=headers)
                        with open(img_name2, "wb") as f:
                            f.write(r.content)
                            log.info("{}下载完成".format(img_name2))

                    except IndexError:
                        # log.info("The list of elements is empty, and no index could be accessed.")
                        continue
                    except Exception:
                        # log.info(f"An error occurred: {e}")
                        continue
                page1.wait_for_timeout(random.randrange(1500, 2500, 1))
                page1.close()


with sync_playwright() as playwright:
    run(playwright)
