import json
from lxml import etree
import pandas as pd
import requests
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
import time


option = webdriver.ChromeOptions()
option.add_experimental_option("detach", True)

# 将option作为参数添加到Chrome中
driver = webdriver.Chrome(options=option, executable_path=r'E:\chromedriver-win64\chromedriver.exe')

driver.get('https://www.tomfordfashion.com/search?q=dress&search-button=&lang=null')
# 定位搜索按钮
button = driver.find_element(By.XPATH, '//*[@id="product-search-results"]/div/div[3]/div/div[19]/div/div/button')
# 执行单击操作
button.click()
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
button2 = driver.find_element(By.XPATH, '//*[@id="product-search-results"]/div/div[3]/div/div[37]/div/div/button')
button2.click()
time.sleep(5)
button2 = driver.find_element(By.XPATH, '//*[@id="product-search-results"]/div/div[3]/div/div[55]/div/div/button')
button2.click()

headers = {
        'Cookie' : 'dwac_6f2238d52d8974f92a11db3d39=up-h06puLz1wgPYrF-7cy2NhIX-pYF2ZadU%3D|dw-only|||USD|false|America%2FNew%5FYork|true; cqcid=achR8VAqUoQTLaBFwLw78GEfIc; cquid=||; dwanonymous_5b9ab30ee20effb1a902cc3794092888=achR8VAqUoQTLaBFwLw78GEfIc; sid=up-h06puLz1wgPYrF-7cy2NhIX-pYF2ZadU; __cq_dnt=0; dw_dnt=0; dwsid=T_DvYNspTVop3ld47HELr5YOb8zYJz_-MIsTzuJSIPSii1V0dBEUjbzumrnWgi2NzTyWyr0apSzQropr8BwNDQ==; _gcl_au=1.1.1296631644.1712480876; _ga=GA1.1.1646785392.1712480878; _fbp=fb.1.1712480879852.1392709787; ftr_ncd=6; __cq_uuid=achR8VAqUoQTLaBFwLw78GEfIc; __cq_seg=; bluecoreNV=true; tracker_device=c2440afb-73f5-4d4e-806b-7ab1f7a8c69a; __cq_bc=%7B%22bkft-tomford%22%3A%5B%7B%22id%22%3A%22ACK182-YAX179%22%7D%5D%7D; mp_tom_ford_us_mixpanel=%7B%22distinct_id%22%3A%20%2218eb7d083471086-084caa31899985-26001a51-1fa400-18eb7d0834811ff%22%2C%22bc_persist_updated%22%3A%201712480879433%7D; _uetsid=5452e0c0f4be11eeb5940514f422e51f; _uetvid=5452efb0f4be11ee9c5faf788167d2ae; bc_invalidateUrlCache_targeting=1712482377745; forterToken=fa4499fddbb24a21b46b1f719568c9ca_1712482377536__UDF43-m4_9ck_; _ga_Z46QV8Q8M8=GS1.1.1712480877.1.1.1712482461.35.0.0',
        'referer' : 'https://www.tomfordfashion.com/search?q=dress&start=0&sz=36',
        'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
       }

file_path = r'E:/Tomford'
for i in range(14, 65):
    element = driver.find_element(By.XPATH,'//*[@id="product-search-results"]/div/div[3]/div/div[{}]/div/div/div[1]/a[1]'.format(i))
    href_value = element.get_attribute('href')
    # print(href_value)
    res = requests.get(url=href_value, headers=headers).text
    tree2 = etree.HTML(res)
    img_name = tree2.xpath('//*[@id="maincontent"]/div/div[1]/div[1]/div/div/div/div/ol/li[3]/span/text()')
    # print(img_name)
    for i in range(1,5):
        img_url2 = tree2.xpath('//*[@class="product-detail product-wrapper "]/div[1]/div[2]/div[1]/section/div[2]/div[{}]/img/@src'.format(i))

        # print(img_name)
        try:
            img_url3 = img_url2[0]
            img_url = img_url3.replace(img_url3.split('?')[-1], 'w=1200')
            print(img_url)
            # print(img_url)
            r = requests.get(url=img_url, headers=headers)
            img_name1 = file_path + '/' + img_name[0] + '{}.jpg'.format(i)
            with open(img_name1, 'wb') as f:
                f.write(r.content)
                print('{}下载完成'.format(img_name1))
        except IndexError:
            print("The list of elements is empty, and no index could be accessed.")
        except NoSuchElementException:
            print("The element with the specified XPath does not exist")
        except Exception as e:
            print(f"An error occurred: {e}")

