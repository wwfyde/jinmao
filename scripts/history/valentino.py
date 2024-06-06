import os

from lxml import etree
import requests
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

option = webdriver.ChromeOptions()
option.add_experimental_option("detach", True)
os.system(r'start chrome --remote-debugging-port=9527 --user-data-dir="E:\selenium"')
option = webdriver.ChromeOptions()
option.add_experimental_option("debuggerAddress", "127.0.0.1:9527")
# 将option作为参数添加到Chrome中
driver = webdriver.Chrome(options=option, executable_path=r"E:\chromedriver-win64\chromedriver.exe")

driver.get("https://www.valentino.com/en-us/search?q=dress&category=2096475")
# 定位搜索按钮
button = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.XPATH, '//*[@id="container-4151dbf100"]/div[1]/section[2]/div/div[2]/p'))
)
# 执行单击操作
driver.execute_script("arguments[0].click()", button)

driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
button2 = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.XPATH, '//*[@id="container-4151dbf100"]/div[1]/section[2]/div/div[2]/p'))
)
# 执行单击操作
driver.execute_script("arguments[0].click()", button2)
time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)

headers = {
    "Cookie": 'affinity="0beb5fb57c66e79a"; vltn_aka_geo=en-us; AKA_A2=A; rskxRunCookie=0; rCookie=4rzrkjnfzqx1fitfcp2e68lutm5ggg; at_check=true; gig_canary=false; gig_canary_ver=15877-3-28545690; AMCVS_49DBA42E58DE4C560A495C19%40AdobeOrg=1; AMCV_49DBA42E58DE4C560A495C19%40AdobeOrg=179643557%7CMCIDTS%7C19824%7CMCMID%7C68434657789480005233216573735574492233%7CMCAAMLH-1713346445%7C7%7CMCAAMB-1713346445%7Cj8Odv6LonN4r3an7LhD3WZrU1bUpAkFkkiY1ncBR96t2PTI%7CMCOPTOUT-1712748845s%7CNONE%7CvVersion%7C5.5.0; _cs_mk_aa=0.6816039072104465_1712741645832; w_session=68434657789480005233216573735574492233.1712741645832; _gid=GA1.2.1592837815.1712741647; _cs_c=1; gig_bootstrap_4_jpzFZXy-UzNbEa96QRLeyA=_gigya_ver4; s_inv=0; s_cc=true; mdLogger=false; kampyle_userid=8f9b-8a71-5ea3-d456-e691-613d-1564-f631; kampyleUserSession=1712741678664; kampyleUserSessionsCount=2; s_sq=%5B%5BB%5D%5D; mbox=session#a22067897f5f4917998514a5827843e7#1712743761; lastRskxRun=1712741902023; _ga_6HNS7HR53T=GS1.1.1712741646.1.1.1712741902.0.0.0; mbox=session#a22067897f5f4917998514a5827843e7#1712743764; _ga_H6H7S9V9E0=GS1.1.1712741646.1.1.1712741904.0.0.0; _ga=GA1.2.2067082227.1712741646; _cs_id=f28b37a3-2358-adff-bcc7-1721d0c1366e.1712741651.1.1712741904.1712741651.1.1746905651037.1; _cs_s=3.0.0.1712743704789; OptanonConsent=isGpcEnabled=0&datestamp=Wed+Apr+10+2024+17%3A38%3A24+GMT%2B0800+(%E4%B8%AD%E5%9B%BD%E6%A0%87%E5%87%86%E6%97%B6%E9%97%B4)&version=202306.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=6da8f137-0830-467d-a12f-481ddcfea76e&interactionCount=1&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A0%2CC0004%3A0&AwaitingReconsent=false; s_nr30=1712741907780-New; s_tslv=1712741907781; s_gpv=V%3AUS%3Aproduct%3ACREPE%20COUTURE%20SHORT%20DRESS%20_BVA1L51CF_157; s_plt=12.52; s_pltp=V%3AUS%3Aproduct%3ACREPE%20COUTURE%20SHORT%20DRESS%20_BVA1L51CF_157; kampyleSessionPageCounter=5; s_prev_pn=item; inside-eu=755466359-3ef7ee2b0a384dca176b61c30cd6f94ae3411fc723bd0b1c2c04014712229805-0-0; RT="z=1&dm=valentino.com&si=18c692e6-a306-4291-b442-4e54d97bee46&ss=lutm4stx&sl=8&tt=290g&bcn=%2F%2F17de4c14.akstat.io%2F&ld=7n4o&ul=c5r8"; ADRUM=s=1712742178086&r=https%3A%2F%2Fwww.valentino.com%2Fen-us%2Fproduct-crepe-couture-short-dress--BVA1L51CF_157',
    "referer": "https://www.valentino.com/en-us/search?q=dress&category=2096475&pagination=3",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
}
img_detail2 = []
file_path = r"E:/valentino"
for i in range(1, 89):
    element = driver.find_element(
        By.XPATH, '//*[@id="container-4151dbf100"]/div[1]/section[2]/ul/li[{}]/div/a'.format(i)
    )
    href_value = element.get_attribute("href")
    # log.info(href_value)
    res = requests.get(url=href_value, headers=headers).text
    tree2 = etree.HTML(res)
    img_name = tree2.xpath('//*[@id="container-d425662105"]/div[2]/div/div[1]/section[1]/article/h1/text()')
    img_detail = tree2.xpath('//*[@id="container-d425662105"]/div[2]/div/div[1]/section[2]/div[2]/div[1]/p[1]/text()')
    img_color = tree2.xpath('//*[@id="container-d425662105"]/div[2]/div/div[3]/section[1]/div[1]/h2/span/text()')
    img_prize = tree2.xpath('//*[@id="container-d425662105"]/div[2]/div/div[1]/section[1]/p/@data-price')
    # log.info(img_name)
    # log.info(img_detail)
    # .replace('\n', '').strip()

    new_folder_name = img_name[0].strip() + "{}".format(i)
    # Full path of the new folder
    new_folder_path = os.path.join(file_path, new_folder_name)
    # Create the new folder if it doesn't exist
    if not os.path.exists(new_folder_path):
        os.makedirs(new_folder_path)
    for img_detail in img_detail:
        img_detail2.append(img_detail.replace("\n", "").strip())
    img_detail2.append(img_color[0])
    img_detail2.append("$" + img_prize[0])
    # log.info(img_detail2)
    # log.info(img_detail2)
    img_detail3 = new_folder_path + "/" + img_name[0].strip() + ".txt"
    with open(img_detail3, "w", encoding="utf-8") as f:
        for string in img_detail2:
            f.write(string + "\n")
        # 写入内容到文件
        # f.write(content)
        log.info("{}下载完成".format(img_detail3))
    img_detail2 = []
    for j in range(1, 6):
        # log.info(href_value2)
        try:
            img_url2 = tree2.xpath(
                '//*[@id="container-d425662105"]/div[2]/div/div[2]/section[1]/div/div[1]/div[{}]/img/@srcset'.format(j)
            )
            # log.info(img_url2)
            href_value2 = img_url2[0].split(" ")[-2].split(",")[1]
            # log.info(img_url)
            r = requests.get(url=href_value2, headers=headers)
            img_name1 = new_folder_path + "/" + img_name[0].strip() + "{}.jpg".format(j)

            with open(img_name1, "wb") as f:
                f.write(r.content)
                log.info("{}下载完成".format(img_name1))

        except IndexError:
            log.info("The list of elements is empty, and no index could be accessed.")
        except NoSuchElementException:
            log.info("The element with the specified XPath does not exist")
        except Exception as e:
            log.info(f"An error occurred: {e}")
