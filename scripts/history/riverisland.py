import json
import os


from lxml import etree
import pandas as pd
import requests
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

option = webdriver.ChromeOptions()
option.add_experimental_option("detach", True)
os.system(r'start chrome --remote-debugging-port=9527 --user-data-dir="D:\wendangDisk\selenium"')
option = webdriver.ChromeOptions()
option.add_experimental_option("debuggerAddress", "127.0.0.1:9527")
# 将option作为参数添加到Chrome中
driver = webdriver.Chrome(options=option, executable_path=r'D:\wendangDisk\chromedriver-win64\chromedriver.exe')
driver.get('https://www.riverisland.com/us/c/women/dresses')

driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
            )
# 执行单击操作
driver.execute_script("arguments[0].click()", button)

driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
button2 = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
            )
# 执行单击操作
driver.execute_script("arguments[0].click()", button2)
time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
button3 = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
            )
# 执行单击操作
driver.execute_script("arguments[0].click()", button3)
time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
button4 = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
            )
# 执行单击操作
driver.execute_script("arguments[0].click()", button4)
time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
button5 = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
            )
# 执行单击操作
driver.execute_script("arguments[0].click()", button5)
time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
button6 = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
            )
# 执行单击操作
driver.execute_script("arguments[0].click()", button6)
time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)

button7 = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
            )
# 执行单击操作
driver.execute_script("arguments[0].click()", button7)
time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)

button8 = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
            )
# 执行单击操作
driver.execute_script("arguments[0].click()", button8)
time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
button9 = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
            )
# 执行单击操作
driver.execute_script("arguments[0].click()", button9)
time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)

headers = {
        'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
       }
img_detail2 = ['main', 'rollover', 'back', 'alt1', 'alt2', 'alt3']
file_path = r'D:\wendangDisk\riverisland'
for i in range(450, 601):
    element = driver.find_element(By.XPATH,'//*[@id="__next"]/div/div[6]/div[2]/a[{}]'.format(i))
    href_value = element.get_attribute('data-id')
    element2 = driver.find_element(By.XPATH, '//*[@id="__next"]/div/div[6]/div[2]/a[{}]/div[2]/h5'.format(i))
    img_name = element.get_attribute('text')
    # print(href_value)
    # print(img_name)
    img_name1 = img_name.split('$')[0]

    for img_detail in img_detail2:
        img_url = 'https://images.riverisland.com/image/upload/t_ProductImagePortraitLarge/{}_{}'.format(href_value, img_detail)
        # print(img_url)
        r = requests.get(url=img_url, headers=headers)

        new_folder_name = img_name1
        # Full path of the new folder
        new_folder_path = os.path.join(file_path, new_folder_name)
        # Create the new folder if it doesn't exist
        if not os.path.exists(new_folder_path):
            os.makedirs(new_folder_path)
        img_name2 = new_folder_path + '/' + img_name1 + '_{}.jpg'.format(img_detail)

        with open(img_name2, 'wb') as f:
            f.write(r.content)
            print('{}下载完成'.format(img_name2))
