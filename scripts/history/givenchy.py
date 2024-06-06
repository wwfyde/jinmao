import os

import requests
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

os.system(r'start chrome --remote-debugging-port=9527 --user-data-dir="E:\selenium"')
option = webdriver.ChromeOptions()
option.add_experimental_option("debuggerAddress", "127.0.0.1:9527")

# option.add_experimental_option("detach", True)

# 将option作为参数添加到Chrome中
driver = webdriver.Chrome(options=option, executable_path=r"E:\chromedriver-win64\chromedriver.exe")

driver.get("https://www.givenchy.com/us/en-US/search?q=dress&page=4")

# window_before = driver.window_handles[0]
# 获取当前页面的总高度


headers = {
    "Cookie": "dwanonymous_29eb3f5ea2674fc92abd2b353de7ae23=abuggIWI3mA42k8Sh608Ruq8p9; dispatchSite=US-en-GIV_US; _abck=557310E1FB1D81986693AD6718654EE2~0~YAAQbRjQF28hU7yOAQAA1ormxQthBxLomAoU88/D+/039f3dBjsilCi6iIMLZPTKnxDPj8pPlLUYzvbUsqconAZVwKIFeBN/rkWptcoOdE9UmfL2b87X0yvu7JoGz9tqNOmE3xS6WyjSPPVatJKrPNKoWNTKzBw/fw1C5Wk71YaL8ttzCkpgRKDM0xOTTDK1GodX2OP0OiuDI+Or10F1HNaLvlEBhoQu6mS4OOhXgz/aSaUs4VmC0+ILwFnqvJlhGh6vWd5D8nNaNa4UXAVbXHbE27zr6L8CphBQZeSHLWWZnhxhT7WA4CjfKzXlK5n6hcv09ZAPvAzzyAhwQGngDpNyUmhzHkVO479mN3RhH8aRmPb4l669JneujKE0FgGVb1n170/wwpFB7jmt+PVn5gd87IRprL9aJiY=~-1~-1~-1; ftr_ncd=6; __cq_uuid=abBSc26GyBKmncwrVJnCbuujEa; _gid=GA1.2.1099303688.1712717161; _gcl_au=1.1.1164021777.1712717161; _scid=512488c3-e383-4087-8682-49da5f9f9cb5; FPID=FPID2.2.UCBYmRoDntcLu9N0EUXXH7M4UHmxfgdeDIStVm%2F2%2Fnk%3D.1712717161; FPLC=oZze9VPW69T25HA5fGUFarBdUGcKkLmByIWTmLKf8XOBC%2BWJ1IvQ57Wtw5tNbDN8qShkW4WgKCBAEasscAByoe2AsapAyKcUkbQeVbNchpEDPnugpJehSGq0h1yynQ%3D%3D; _fbp=fb.1.1712717164905.303805223; _tt_enable_cookie=1; _ttp=InYOPBzPkRI9GFCpUrAWBAywQFv; _sctr=1%7C1712678400000; bm_mi=F294885A322D02611D4BFA3FBCF7F461~YAAQHQXGF4wcTb6OAQAAqq5YxhdXhrbQ+94nnmoJSDevYnV8wgAeYnYA/y5KqWai7vcKa82dOiUATf9o7gJaq/OMYeBOT6S2eIOSZ8DXi7XL2jqFPHM4UCy8c/6lSkKxsYUkPqz6CDmK5kD7/CWumK7dMNKL0CphfBr5gmGSlfPRjAF8UcSY4LtQ0mtRsHPgt0MqQy5na3vwb/30ISumai22MMO5ZZqRJF0/sjcs5I9s0koIJt3p5QxlIaRIfjjODRASJgqDi2/J9jS+UcNyVrgdT57wATpifIN8LTyFXg8n7D0RC/sizTEN419Agm8r0SemYZLnharDMCGBaoQ+~1; ak_bmsc=7C93C8FB2BD9770E54641558687112FA~000000000000000000000000000000~YAAQHQXGF7EcTb6OAQAAzLNYxhfR3tVKBSkpjqGXEjDS6QdvOR+UYAAnwhPRqftAlTWDRYSrtYjDiUtFocoibg0I+gFNMzGQcB7aC9NkmSy6MzVx+fDyb7+a1KWicSxtuhlH44fJy8HJFeNGqWSvY8vYskCflMlc4HRB+lvQsaAr+fq4sD3vGuUbXHpqPV2gboywHxbeYdG8Gb80vlE3f1/4xn23I7Mm4GhnF0F+DxBwMslstdItRFAeeIGHwLR5Mi0tG1+l+r04zFVrZy3RUUEFwINJTdiswfd6xhTD/X4LjT74h9QMaDeD5T780JadMk11aM6oVE9pdxac5ynevTEWHcAa4GQ4PgtLxhdLJ/oQK3EUcRUgsJ5mXl/lUm4sTne2Z5UY7pwkufcJLE1u1Hza2/dvWutqOF1byqxiXv7ecaBDePn+9QcqKexiI0dRS9jvtNJyVP9j5QYwz9Z7FkghZKF6xIdQWWT6yd/1ic1QwSnXpoWRYcrQo/2cDpgvjw==; __cq_bc=%7B%22bbrt-GIV_US%22%3A%5B%7B%22id%22%3A%22BW21LX4ZGS%22%2C%22type%22%3A%22vgroup%22%2C%22alt_id%22%3A%22BW21LX4ZGS-004%22%7D%2C%7B%22id%22%3A%22BW21YK15BG%22%2C%22type%22%3A%22vgroup%22%2C%22alt_id%22%3A%22BW21YK15BG-001%22%7D%2C%7B%22id%22%3A%22BW21Z114TF%22%2C%22type%22%3A%22vgroup%22%2C%22alt_id%22%3A%22BW21Z114TF-100%22%7D%2C%7B%22id%22%3A%22BW221C61G9%22%2C%22type%22%3A%22vgroup%22%2C%22alt_id%22%3A%22BW221C61G9-001%22%7D%2C%7B%22id%22%3A%22BW21V0G1N1%22%2C%22type%22%3A%22vgroup%22%2C%22alt_id%22%3A%22BW21V0G1N1-001%22%7D%2C%7B%22id%22%3A%22BW221E30XH%22%2C%22type%22%3A%22vgroup%22%2C%22alt_id%22%3A%22BW221E30XH-001%22%7D%2C%7B%22id%22%3A%22BW221K30XH%22%2C%22type%22%3A%22vgroup%22%2C%22alt_id%22%3A%22BW221K30XH-545%22%7D%2C%7B%22id%22%3A%22BW21P94ZJP%22%2C%22type%22%3A%22vgroup%22%2C%22alt_id%22%3A%22BW21P94ZJP-001%22%7D%2C%7B%22id%22%3A%22BW21XA15JC%22%2C%22type%22%3A%22vgroup%22%2C%22alt_id%22%3A%22BW21XA15JC-545%22%7D%2C%7B%22id%22%3A%22BW222714V8%22%2C%22type%22%3A%22vgroup%22%2C%22alt_id%22%3A%22BW222714V8-100%22%7D%5D%7D; __cq_seg=0~0.37!1~-0.52!2~0.61!3~0.12!4~0.20!5~-0.12!6~-0.21!7~-0.14!8~-0.12!9~-0.27!f0~15~5; dwac_dbce18704150c897de303bd610=e9O60R_tpMFKt3iL9izrMF641KBnUKM2Rak%3D|dw-only|||USD|false|America%2FNew%5FYork|true; cqcid=abuggIWI3mA42k8Sh608Ruq8p9; cquid=||; sid=e9O60R_tpMFKt3iL9izrMF641KBnUKM2Rak; __cq_dnt=0; dw_dnt=0; dwsid=qfP1s_NXrb2hvWIt2jRqS4yYm8KL6qpKrqOX355ZpoENuiDC3DPrQEKHP-jzJ-eelVXNnqGo-yxxATWJ6o6FVA==; bm_sz=7B221811E4C20DB3FCAF52C27858A23F~YAAQQAXGFyuzK5qOAQAAQwBoxheAH9YIubrYaCUSeiVCwXiEyROnZJSmONQjmSO5WEtw5tvFVgMzN1CsMQ8I9zQdqv2dkX1mAjuVLtUUC+6JKjZOZsZ59bMbqIyrQklqTJyTz70bDPO/ULtriJuodGXrWF45U38etygbg69wZUayCHkxBY7E+eOwGW8mgmdNmLXU18tTvKn6AW4n2/voDlvnkqCNQ61JqXK+t3fetZy+quURp9rPlBM5qMkRYr0zNBWjeCofxV1Ra015uZwOm4NepwfbkbLMFdUb1i3BJ54AC+9Fz+gWjRks8L2kbB+jqtTkTBV1r5ybUtXuIsnGngCOwf9Xdgt04r87XtJvvLrad7tXs9EhLeH0n0vgNso4W5g4Dw/fZSBJtQwvuzTFZZILZu4vyIFJ/IL9smFyQMQjFKjb8O4tY6W4lH4IXoo106A/tnR9UEd9nVLhKNZ0IetRhF6+gNybqTbScR5MmeckkS6e5hd2ATWbBmjosFHdEtqF+vQLTuySNcoMq2fJS51y5NWBOb5TFr7VwvHLYGvUVXNd0w6C~3687991~4470071; _uetsid=780f5d00f6e411ee819be13fa23ef5ff; _uetvid=780f84b0f6e411ee97dc93a2b88f59a6; OptanonConsent=isGpcEnabled=0&datestamp=Wed+Apr+10+2024+13%3A06%3A30+GMT%2B0800+(%E4%B8%AD%E5%9B%BD%E6%A0%87%E5%87%86%E6%97%B6%E9%97%B4)&version=202308.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=33761383-9bb0-4ce4-9d50-dc561708d359&interactionCount=1&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1%2CC0005%3A1&AwaitingReconsent=false; _scid_r=512488c3-e383-4087-8682-49da5f9f9cb5; forterToken=f5be031b359a4c048e98b23e8e7991c5_1712725588211__UDF43-m4_9ck_; _ga=GA1.2.276016704.1712717161; _ga_5D5QSS8DSD=GS1.1.1712717159.1.1.1712725608.0.0.215206473; bm_sv=30A267229860F3FF7C4DECF7B09BEB09~YAAQoHxCF1sqqcSOAQAAGWRoxhedASGRq6e8lSG9ckqLPwA78COEUyqpVEdNimJO02RVwk/UJCL3pLmiKSq48zjxLUeutqK2TnLOCQwJ4buRFR/tWLnBYHDjVacJaxXAgUDZHS92y3anAvatw3s5yDqFAYpDUctYFeWSLJpefnlp3U0nMCf6LSE2j7tqobA+rjDjZgBdsdhsv3TnKOvClBGo9IbVfw4tyXmRlSQm2olE28LEtPfYOiVkTTIRA9IFGBeGbg==~1; _gat_UA-23083189-1=1",
    "referer": "https://www.givenchy.com/us/en-US/search?q=dress&page=2",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
}

file_path = r"E:/givenchy"

for i in range(55, 78):
    button3 = WebDriverWait(driver, 60).until(
        EC.presence_of_element_located(
            (By.XPATH, '//*[@id="primary"]/div[2]/div[2]/div/ul/li[{}]/div/figure/a/span/span[1]/img'.format(i))
        )
    )
    # 执行单击操作
    driver.execute_script("arguments[0].click()", button3)
    time.sleep(5)
    # window_after = driver.window_handles[i]
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
        EC.presence_of_element_located((By.XPATH, '//*[@id="product-content"]/div[1]/div/h1'))
    )
    img_name = img_name2.text
    log.info(img_name)
    # img_name = tree2.xpath('//*[@id="main"]/div[1]/div[2]/div/div[1]/div[1]/div[1]/div/div/h1/span[1]/text()')
    # log.info(img_name)
    # # 定位搜索按钮
    try:
        for i in range(1, 7):
            img_url2 = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        '//*[@id="product-container"]/div[1]/div[1]/section/div[2]/ul/li[{}]/div/button/img'.format(i),
                    )
                )
            )
            href_value2 = img_url2.get_attribute("srcset")
            img_url = href_value2.split(" ")[-2]
            # 定位搜索按钮
            # log.info(img_url)
            # log.info(href_value2)

            r = requests.get(url=img_url, headers=headers)

            new_folder_name = img_name.rstrip()
            # Full path of the new folder
            new_folder_path = os.path.join(file_path, new_folder_name)
            # Create the new folder if it doesn't exist
            if not os.path.exists(new_folder_path):
                os.makedirs(new_folder_path)
            img_name1 = new_folder_path + "/" + img_name.rstrip() + "{}.jpg".format(i)

            with open(img_name1, "wb") as f:
                f.write(r.content)
                log.info("{}下载完成".format(img_name1))
    except IndexError:
        log.info("The list of elements is empty, and no index could be accessed.")
    except NoSuchElementException:
        log.info("The element with the specified XPath does not exist")
    except Exception as e:
        log.info(f"An error occurred: {e}")

    time.sleep(5)
    driver.back()

#
