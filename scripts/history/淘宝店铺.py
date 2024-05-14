import os
import re
from playwright.sync_api import Playwright, sync_playwright, expect
from lxml import etree
import requests
file_path = r'C:\爬虫图片\衣服\伦小妞'


headers = {
    'Cookie' : 'xlly_s=1; lid=tb780422052; _l_g_=Ug%3D%3D; lgc=tb780422052; cookie3_bak=1dcc33a4f2070b351b715f7d09fa8e9e; cookie1=UNRkgCrrUlSwf3I05o5zfKUsRnQDFsasqMcLXwB2iEE%3D; login=true; cookie2=1dcc33a4f2070b351b715f7d09fa8e9e; env_bak=FM%2BgywHD45XwpbBMXUlRhbnnGWOdMs7nFkhjFkxAb2pK; cancelledSubSites=empty; sg=26a; sn=; _tb_token_=ee73e8e1e7571; wk_unb=UUphzOff%2BfEYEvZVeQ%3D%3D; dnk=tb780422052; uc1=pas=0&existShop=false&cookie16=UIHiLt3xCS3yM2h4eKHS9lpEOw%3D%3D&cookie14=UoYfpCd98%2B49DQ%3D%3D&cookie15=VT5L2FSpMGV7TQ%3D%3D&cookie21=V32FPkk%2FgPzW; uc3=lg2=WqG3DMC9VAQiUQ%3D%3D&id2=UUphzOff%2BfEYEvZVeQ%3D%3D&vt3=F8dD3exB0yz%2BOO2zuTM%3D&nk2=F5RCbbyMsDCw3Ws%3D; tracknick=tb780422052; uc4=id4=0%40U2grF8wSVF1w0zUbSpPKushVx55eFxiu&nk4=0%40FY4Jg5WwN8w7pFy4V6XxSYE%2FcS1bew%3D%3D; unb=2206510437106; cookie17=UUphzOff%2BfEYEvZVeQ%3D%3D; wk_cookie2=1b16f6e549d57fdcc42651509bb93c31; _nk_=tb780422052; sgcookie=E100klUX7yUZJZWECqH2%2FZL2IIPi4%2FlVEwz8tvj4jqv4qVIVlNwdtwHTDWbBoS8EpaMrTtgq2AxQrJPY9gXzMCeEJFX3U1HAyk8Psm%2BotFlML%2BZ%2BBtEaU3YMzMld8rdPbO21; t=61baaa00b18ef310857c0304d8bbb8db; csg=b573e3a7; cookie3_bak_exp=1715309141390; cna=KNq0Hrc5hlACAXxapaxe7vQX; arms_uid=913cd9da-2ad6-4f27-8d21-2a74b356bbc6; tfstk=fCOmtJmkEKWXQuUtmQfjap3B16k8co11jhFOX1IZUgSW6KIthf0GqeWxlhK9EGxyqi8AXqOMEnTFHhYslNSwbhj9HYhplE11_DCi9XLjCqtPMIfaXUlwWcrrvXhpu7AmACmK5ooYaGbN_ZW4_gulSw7N_tW4a4bNWoyagh8rrNsPu-7agT7P5N_qikFNxCRWa2d79akkhLRlotkJugPNPQbcnM82i5PadZXcYESovYABkT81ICa_sOY2dh_e0oodhFJkqZfiw-5erd-hPIlLma9vzeIy-PN6lsbGL1Wu758lGgWpg6lUqa9ykdRXmPVNlIddIM6o756OaBBeLn4sRU5V7h6B6DNf0F8BOpCnw-5erd-HIgrTUJSGO5_rWQy_Ct75rMg4nNmXapAar40udx6VPZnKr42_Ct75rM3orJZ13a_xv; isg=BPLyLuz0wDZDwvwcB5j0GtmbQzjUg_YdLeY0CbzLHqWQT5JJpBNGLfitO-tzP261',
    'Referer' : 'https://shopsearch.taobao.com/',
    'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
}
def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://shop100518951.taobao.com/?spm=pc_detail.27183998/evo365560b447257.202202.1.6b427dd6DQJ6bX#/")
    page.wait_for_timeout(10000)
    for y in range(1,85):
        # page.goto("https://login.taobao.com/member/login.jhtml?redirectURL=https%3a%2f%2fshwin.taobao.com:443/search.htm%2F_____tmd_____%2Fpage%2Flogin_jump%3Frand%3DS3WxGHAgAt756EpznwfNzJq2AFA2qBNla3j6EINUS8We9dazM_iKElp8DwVSHZUevpC41Bx7RzivXIj9RnZgdg%26_lgt_%3D1fad77f53b7664b2acc9dfaa4be4ea6a___220409___869c56a0ac3552bab8aebfefb301575e___eaebc79cac1eb5d2f7d8b4595e00ec73344a42d5a0b8cf56539c823cd24ac06c4d21058431ad70e45dea6b2fa0159a4c2d0a6d16055bf2b9daf604640c9df926edab6949f99c3ed45a5b7ae882a6398d36bcd2c97d15a129973c9575dead2965f30d05b945a6f833c995602b2cac735445c409a1bd8d83f0f1917a93a9ddc72bcf69b43df9d2bf64d2ed7dd91894c71ce678fa7bb3dd0a2e4529713eb2555f8d4947a01f65db828f5a70cc62d4f5a53c3faf81fbc3eb96d746f5cfb4ae605e58c35c7f7fb3a7518b57ada32a7dd5331c3324f4eeb0c568ee25b866619f48bfbe11bddf804d938cc3c9e007ed406ef75c8aa0b7180dc7653326aff73ec2bedc7cd4bbca6c4a030926b297ad57f54e11ce8a9cf03e03002be0dab1fe0ca8036500424c26ff253bb5859d0a5992a3ce6da0&uuid=1fad77f53b7664b2acc9dfaa4be4ea6a")

        page.locator(
            "#shop-container > div.BasicLayout--mainContent--s8F4rdz > div > div.ItemList--itemList--s7z5wkA > div:nth-child(2) > div.ItemList--pagination--g5giygA > div.ItemList--pageDown--uVfM19F.false").click()
        # page.get_by_role("button", name="保持", exact=True).click()
        page.wait_for_timeout(5000)
        for i in range(1,21):
            with page.expect_popup() as page1_info:
                page.locator("#shop-container > div.BasicLayout--mainContent--s8F4rdz > div > div.ItemList--itemList--s7z5wkA > div:nth-child(2) > div.ItemList--list--mOasvFR > div:nth-child({}) > div".format(i)).first.click()
            page1 = page1_info.value
            page1.wait_for_timeout(5000)

            html = page1.content()
            # print(html)
            tree = etree.HTML(html)
            img_name = tree.xpath('//*[@id="root"]/div/div[2]/div[2]/div[1]/div/div[2]/div[1]/h1/text()')[0]
            img_name = img_name.replace('|', '')
            # amount = tree.xpath('//*[@id="root"]/div/div[2]/div[2]/div[1]/div/div[2]/div[1]/div/span/text()')[0]
            # print(amount)
            # if int(amount.split(' ')[-1].replace('+', '')) >= 100:
            #     img_name = img_name + ' ' + amount
            # print(img_name)
            new_folder_name = img_name
            # Full path of the new folder
            new_folder_path = os.path.join(file_path, new_folder_name)
            # Create the new folder if it doesn't exist
            if not os.path.exists(new_folder_path):
                os.makedirs(new_folder_path)
            for x in range(1, 7):
                try:
                    img_url = tree.xpath(
                        '/html/body/div[3]/div/div[2]/div[2]/div[1]/div/div[1]/div/ul/li[{}]/img/@src'.format(x))[0]
                    # print(img_url)
                    img_url = 'https:' + img_url[:-23]
                    # print(img_url)
                    img_name1 = new_folder_path + '/' + img_name + '{}.jpg'.format(x)
                    r = requests.get(url=img_url, headers=headers)
                    with open(img_name1, 'wb') as f:
                        f.write(r.content)
                        print('{}下载完成'.format(img_name1))

                except IndexError:
                    # print("The list of elements is empty, and no index could be accessed.")
                    continue
                except Exception as e:
                    # print(f"An error occurred: {e}")
                    continue
            page1.wait_for_timeout(2000)
            page1.close()

with sync_playwright() as playwright:
    run(playwright)
