import os

import requests

from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

os.system(r'start chrome --remote-debugging-port=9527 --user-data-dir="D:\test\pythonProject\selenium"')
option = webdriver.ChromeOptions()
option.add_experimental_option("debuggerAddress", "127.0.0.1:9527")

# option.add_experimental_option("detach", True)

headers = {
    "Cookie": "receive-cookie-deprecation=1; id=22bf51af97ef0048||t=1712737956|et=730|cs=002213fd480cc5ce3696545ad9",
    "referer": "https://eu.louisvuitton.com/eng-e1/products/tweed-pocket-dress-nvprod4880029v/1AFF91",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
}

# get直接返回，不再等待界面加载完成
desired_capabilities = DesiredCapabilities.CHROME
desired_capabilities["pageLoadStrategy"] = "none"
# 将option作为参数添加到Chrome中
driver = webdriver.Chrome(options=option, executable_path=r"D:\test\pythonProject\chromedriver.exe")
url = "https://eu.louisvuitton.com/eng-e1/search/WOMEN%20Dresses"
driver.get(url=url)
# driver.maximize_window()
time.sleep(5)
# 定位搜索按钮
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
# 获取当前页面的总高度
button = WebDriverWait(driver, 60).until(
    EC.presence_of_element_located(
        (By.XPATH, "/html/body/div[2]/div/div/main/div[2]/div/div[3]/div/div/div/div/div[1]/button")
    )
)
# 执行单击操作
driver.execute_script("arguments[0].click()", button)

time.sleep(5)
# 定位搜索按钮
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
# 获取当前页面的总高度
button2 = WebDriverWait(driver, 60).until(
    EC.presence_of_element_located(
        (By.XPATH, "/html/body/div[2]/div/div/main/div[2]/div/div[3]/div/div/div/div/div[1]/button")
    )
)
# 执行单击操作
driver.execute_script("arguments[0].click()", button2)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)
driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
time.sleep(5)

file_path = r"D:\test\pythonProject\LV"

for i in range(170, 181):
    # 执行单击操作

    button3 = WebDriverWait(driver, 60).until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "/html/body/div[2]/div/div/main/div[2]/div/div[3]/div/div/div/div/ul/li[{}]/div/div[2]/div[1]/div[1]/div/h2/a".format(
                    i
                ),
            )
        )
    )
    # 执行单击操作
    driver.execute_script("arguments[0].click()", button3)
    time.sleep(5)

    # 定位搜索按钮
    scroll_height = 200
    scroll_pause_time = 0.3  # 滚动后等待的时间，以秒为单位

    # 获取当前页面的总高度
    total_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        # 逐步滚动页面
        driver.execute_script(f"window.scrollBy(0, {scroll_height});")

        # 等待内容加载
        time.sleep(scroll_pause_time)

        # 更新已滚动的高度
        scrolled_height = driver.execute_script("return window.pageYOffset;") + driver.execute_script(
            "return window.innerHeight;"
        )

        # 检查是否已滚动到页面底部
        if scrolled_height >= total_height:
            break

        # 更新总高度，以防页面加载了更多内容
        total_height = driver.execute_script("return document.body.scrollHeight")
    img_name2 = WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.XPATH, '//*[@id="main"]/div[2]/div/section/div[2]/div/div/div[1]/h1'))
    )
    img_name = img_name2.text
    log.info(img_name)
    # img_name = tree2.xpath('//*[@id="main"]/div[1]/div[2]/div/div[1]/div[1]/div[1]/div/div/h1/span[1]/text()')
    # log.info(img_name)
    # # 定位搜索按钮

    for i in range(1, 7):
        try:
            img_url2 = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        '//*[@id="main"]/div[2]/div/section/div[1]/div/div/ul/li[{}]/button/div/picture/img'.format(i),
                    )
                )
            )
            href_value2 = img_url2.get_attribute("srcset")
            # log.info(type(href_value2))
            img_url = href_value2.split(" ")[-2]
            log.info(img_url)
            # 定位搜索按钮
            # log.info(img_url2)
            # log.info(href_value2)

            r = requests.get(url=img_url, headers=headers)

            new_folder_name = img_name.strip()
            # Full path of the new folder
            new_folder_path = os.path.join(file_path, new_folder_name)
            # Create the new folder if it doesn't exist
            if not os.path.exists(new_folder_path):
                os.makedirs(new_folder_path)
            img_name1 = new_folder_path + "/" + img_name.strip() + "{}.jpg".format(i)
            # log.info(img_name1)
            with open(img_name1, "wb") as f:
                f.write(r.content)
                log.info("{}下载完成".format(img_name1))
            detail = new_folder_path + "/" + img_name.strip() + ".txt"
            # with open(detail, 'wb') as f:
            #     f.write(img_name)
        except IndexError:
            log.info("The list of elements is empty, and no index could be accessed.")
        except NoSuchElementException:
            log.info("The element with the specified XPath does not exist")
        except Exception as e:
            log.info(f"An error occurred: {e}")

    driver.implicitly_wait(5)
    driver.back()

#
