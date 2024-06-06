import os
from lxml import etree
import requests
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
import time

option = webdriver.ChromeOptions()
option.add_experimental_option("detach", True)

# 将option作为参数添加到Chrome中
driver = webdriver.Chrome(options=option, executable_path=r"E:\chromedriver-win64\chromedriver.exe")

driver.get("https://us.lanvin.com/search?q=Dress&options%5Bprefix%5D=last")
time.sleep(5)
# 定位搜索按钮
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
button = driver.find_element(By.XPATH, '//*[@id="loadmore-button"]')
driver.implicitly_wait(5)
# 执行单击操作
button.click()

time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
button2 = driver.find_element(By.XPATH, '//*[@id="loadmore-button"]')
driver.implicitly_wait(5)
button2.click()

headers = {
    "Cookie": "secure_customer_sig=; localization=US; cart_currency=USD; _cmp_a=%7B%22purposes%22%3A%7B%22a%22%3Atrue%2C%22p%22%3Atrue%2C%22m%22%3Atrue%2C%22t%22%3Atrue%7D%2C%22display_banner%22%3Afalse%2C%22sale_of_data_region%22%3Afalse%7D; _tracking_consent=%7B%22con%22%3A%7B%22CMP%22%3A%7B%22m%22%3A%22%22%2C%22a%22%3A%22%22%2C%22p%22%3A%22%22%2C%22s%22%3A%22%22%7D%7D%2C%22region%22%3A%22USIL%22%2C%22reg%22%3A%22%22%2C%22v%22%3A%222.1%22%7D; _shopify_y=9881e76f-502c-49b9-a34e-3b4e0c3068bb; _orig_referrer=; _landing_page=%2Fsearch%3Fq%3DDress%26options%255Bprefix%255D%3Dlast; receive-cookie-deprecation=1; _shopify_sa_p=; kaktuspCurrentShownPerMonth=0; kaktuspStartDatePerMonth=Mon%2C%2008%20Apr%202024%2006%3A47%3A18%20GMT; kaktuspCurrentShownPerDay=0; kaktuspStartDatePerDay=Mon%2C%2008%20Apr%202024%2006%3A47%3A18%20GMT; _gcl_au=1.1.375389967.1712558838; _gid=GA1.2.2052284629.1712558839; shopify_pay_redirect=pending; _fbp=fb.1.1712558841464.1119809778; _tt_enable_cookie=1; _ttp=75N09ZKvsH1M3hFfz-aCc7lmqGr; tfpsi=f3b90045-f1d0-44ae-a2fa-84de5db383cd; _hjSession_3418970=eyJpZCI6ImRhNWFlNjMwLWM1M2MtNGMzOS1iMmU1LTcyNzc2OWQxODUwNCIsImMiOjE3MTI1NTg4NDQ2ODIsInMiOjAsInIiOjAsInNiIjowLCJzciI6MCwic2UiOjAsImZzIjoxLCJzcCI6MH0=; __zlcmid=1LBmd3TRdFGSVq7; locale_bar_accepted=1; OptanonAlertBoxClosed=2024-04-08T06:47:31.254Z; _shopify_s=9b6a04ad-c5a0-4a79-8cd3-a658ec6c864b; _shopify_sa_t=2024-04-08T06%3A48%3A50.561Z; mp_92a9c3aa7436b768f5a29bf1741171bd_mixpanel=%7B%22distinct_id%22%3A%20%22%24device%3A18ebc760d0418ae-0cac335c88668c-26001a51-1fa400-18ebc760d0418ae%22%2C%22%24device_id%22%3A%20%2218ebc760d0418ae-0cac335c88668c-26001a51-1fa400-18ebc760d0418ae%22%2C%22%24initial_referrer%22%3A%20%22%24direct%22%2C%22%24initial_referring_domain%22%3A%20%22%24direct%22%2C%22__mps%22%3A%20%7B%7D%2C%22__mpso%22%3A%20%7B%22%24initial_referrer%22%3A%20%22%24direct%22%2C%22%24initial_referring_domain%22%3A%20%22%24direct%22%7D%2C%22__mpus%22%3A%20%7B%7D%2C%22__mpa%22%3A%20%7B%7D%2C%22__mpu%22%3A%20%7B%7D%2C%22__mpr%22%3A%20%5B%5D%2C%22__mpap%22%3A%20%5B%5D%7D; _ga=GA1.2.20762776.1712558839; keep_alive=8e2c7b16-4e6f-47cd-8085-cb2c54cdfc70; OptanonConsent=isIABGlobal=false&datestamp=Mon+Apr+08+2024+14%3A48%3A52+GMT%2B0800+(%E4%B8%AD%E5%9B%BD%E6%A0%87%E5%87%86%E6%97%B6%E9%97%B4)&version=202209.1.0&hosts=&consentId=c7c89b38-9430-47e6-bd2b-e31bdf7508cd&interactionCount=1&landingPath=NotLandingPage&groups=C0002%3A1%2CC0003%3A1%2CC0001%3A1&geolocation=US%3BIL&AwaitingReconsent=false; _hjSessionUser_3418970=eyJpZCI6IjdhNjIzNzU2LTU3N2EtNTk4OS05ZmFmLWY1NjNjZGFiNDcxZCIsImNyZWF0ZWQiOjE3MTI1NTg4NDQ2ODIsImV4aXN0aW5nIjp0cnVlfQ==; cto_bundle=K3HS9F9BaVZ2bGZxYlAlMkJkWmJWaXhyJTJCd1VjYiUyRkQzMHdXcmVsVW1POGduVlg5S2Z0eGIlMkJmcUhUemMxNGl2TU8wM2JaamtDcFlEY01uYmglMkJ6a2hxM2NlZ0VqQms0YzIyMVJPVTdiSG0lMkJlVTZwT241dEFXRGpZaEFwRlIwOHlEeWI0YTNYYkp3QldIU0RqUCUyRmlqd3NOZkVjcEp0dyUzRCUzRA; _ga_5HWWHT566V=GS1.1.1712558838.1.1.1712558933.58.0.0; _ga_ZVFLN9B4R5=GS1.1.1712558838.1.1.1712559077.60.0.0",
    "referer": "https://us.lanvin.com/products/short-dress-in-charmeuse-rw-dr209u-4778-h20001?_pos=1&_sid=8e080bdc1&_ss=r",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
}

file_path = r"E:/lanvin"

for i in range(1, 49):
    element = driver.find_element(By.XPATH, '//*[@id="collection-grid"]/div[{}]/div/div[2]/div/p/a'.format(i))
    href_value = element.get_attribute("href")
    log.info(href_value)
    # href_value = 'https://us.lanvin.com/products/short-dress-in-charmeuse-rw-dr209u-4778-h20001?_pos=1&_sid=8e080bdc1&_ss=r'
    res = requests.get(url=href_value, headers=headers).text
    # log.info(res)
    tree2 = etree.HTML(res)
    img_name = tree2.xpath(
        '//*[@id="shopify-section-template--17641384411382__main"]/section/div[1]/nav/ol/li[2]/a/text()'
    )
    log.info(img_name)
    try:
        for i in range(1, 7):
            img_url2 = tree2.xpath(
                '//*[@id="shopify-section-template--17641384411382__main"]/section/div[3]/div[1]/div/div[{}]/div[1]/a/@href'.format(
                    i
                )
            )
            img_url = "https:" + img_url2[0]
            log.info(img_url)
            r = requests.get(url=img_url, headers=headers)

            new_folder_name = img_name[0]
            # Full path of the new folder
            new_folder_path = os.path.join(file_path, new_folder_name)
            # Create the new folder if it doesn't exist
            if not os.path.exists(new_folder_path):
                os.makedirs(new_folder_path)
            img_name1 = new_folder_path + "/" + img_name[0] + "{}.jpg".format(i)

            with open(img_name1, "wb") as f:
                f.write(r.content)
                log.info("{}下载完成".format(img_name1))
    except IndexError:
        log.info("The list of elements is empty, and no index could be accessed.")
    except NoSuchElementException:
        log.info("The element with the specified XPath does not exist")
    except Exception as e:
        log.info(f"An error occurred: {e}")

#
#


#
#             img_name1 = new_folder_path + '/' + img_name[0] + '{}.jpg'.format(i)
#             with open(img_name1, 'wb') as f:
#                 f.write(r.content)
#                 log.info('{}下载完成'.format(img_name1))
#
