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

driver.get("https://www.chloe.com/us/chloe/shop-online/women/dresses")
# 定位搜索按钮
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
button = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.XPATH, '//*[@id="main"]/div[1]/section[2]/div/footer/div[2]/button'))
)
# 执行单击操作
driver.execute_script("arguments[0].click()", button)

driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
button2 = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.XPATH, '//*[@id="main"]/div[1]/section[2]/div/footer/div[2]/button'))
)
# 执行单击操作
driver.execute_script("arguments[0].click()", button2)
time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
}
img_detail2 = []
file_path = r"E:/chloe"
for i in range(1, 54):
    element = driver.find_element(By.XPATH, '//*[@id="products"]/article[{}]/a'.format(i))
    href_value = element.get_attribute("href")
    # log.info(href_value)
    res = requests.get(url=href_value, headers=headers).text
    tree2 = etree.HTML(res)
    img_name = tree2.xpath('//*[@id="main"]/article/div[2]/div/div[1]/h1/text()')
    img_detail = tree2.xpath('//*[@id="tabs"]/div[1]/div[2]/div/span/div/text()')[-1]
    # img_color = tree2.xpath('//*[@id="main"]/article/div[2]/div/div[1]/p/text()')
    # img_prize = tree2.xpath('//*[@id="main"]/article/div[2]/div/div[1]/div[1]/div/div/div/span/span[2]/@data-ytos-price')
    # # log.info(img_detail)
    # log.info(img_color)
    # log.info(img_prize)
    # log.info(img_name)
    # log.info(img_name)
    # log.info(img_detail)
    # .replace('\n', '').strip()

    new_folder_name = img_name[0].strip() + "{}".format(i)
    # Full path of the new folder
    new_folder_path = os.path.join(file_path, new_folder_name)
    # Create the new folder if it doesn't exist
    if not os.path.exists(new_folder_path):
        os.makedirs(new_folder_path)
    img_detail.replace("\r", "")
    img_detail2.append(img_detail.replace("\n", "").strip())
    # log.info(img_detail2)
    # img_detail2.append(img_color[0])
    # img_detail2.append('$' + img_prize[0])

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
    for j in range(3, 11):
        # log.info(href_value2)
        try:
            img_url2 = tree2.xpath(
                '//*[@id="main"]/article/div[1]/div/div[2]/div[1]/div[{}]/picture/img/@data-src'.format(j)
            )

            # log.info(img_url2)
            href_value2 = img_url2[0]
            href_value3 = "https://www.chloe.com/product_image/{}/f/w1536.jpg".format(href_value2.split("/")[-3])
            log.info(href_value2)
            # log.info(img_url)
            r = requests.get(url=href_value2, headers=headers)
            img_name1 = new_folder_path + "/" + img_name[0].strip() + "{}.jpg".format(j)
            r1 = requests.get(url=href_value3, headers=headers)
            img_name3 = new_folder_path + "/" + img_name[0].strip() + "1.jpg"

            with open(img_name3, "wb") as f:
                f.write(r1.content)
                log.info("{}下载完成".format(img_name3))
            with open(img_name1, "wb") as f:
                f.write(r.content)
                log.info("{}下载完成".format(img_name1))

        except IndexError:
            log.info("The list of elements is empty, and no index could be accessed.")
        except NoSuchElementException:
            log.info("The element with the specified XPath does not exist")
        except Exception as e:
            log.info(f"An error occurred: {e}")
