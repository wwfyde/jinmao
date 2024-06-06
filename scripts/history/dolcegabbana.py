import os

from selenium import webdriver
from selenium.webdriver.common.by import By

option = webdriver.ChromeOptions()
option.add_experimental_option("detach", True)
os.system(r'start chrome --remote-debugging-port=9527 --user-data-dir="D:\wendangDisk\selenium"')
option = webdriver.ChromeOptions()
option.add_experimental_option("debuggerAddress", "127.0.0.1:9527")
# 将option作为参数添加到Chrome中
driver = webdriver.Chrome(options=option, executable_path=r"D:\wendangDisk\chromedriver-win64\chromedriver.exe")
driver.get("https://www.dolcegabbana.com/en-us/fashion/women/clothing/dresses/")

# driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
# time.sleep(5)
# button = WebDriverWait(driver, 10).until(
#                 EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
#             )
# # 执行单击操作
# driver.execute_script("arguments[0].click()", button)
#
# driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
# time.sleep(5)
# button2 = WebDriverWait(driver, 10).until(
#                 EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
#             )
# # 执行单击操作
# driver.execute_script("arguments[0].click()", button2)
# time.sleep(5)
# driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
# time.sleep(5)
# button3 = WebDriverWait(driver, 10).until(
#                 EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
#             )
# # 执行单击操作
# driver.execute_script("arguments[0].click()", button3)
# time.sleep(5)
# driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
# time.sleep(5)
# button4 = WebDriverWait(driver, 10).until(
#                 EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
#             )
# # 执行单击操作
# driver.execute_script("arguments[0].click()", button4)
# time.sleep(5)
# driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
# time.sleep(5)
# button5 = WebDriverWait(driver, 10).until(
#                 EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
#             )
# # 执行单击操作
# driver.execute_script("arguments[0].click()", button5)
# time.sleep(5)
# driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
# time.sleep(5)
# button6 = WebDriverWait(driver, 10).until(
#                 EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
#             )
# # 执行单击操作
# driver.execute_script("arguments[0].click()", button6)
# time.sleep(5)
# driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
# time.sleep(5)
#
# button7 = WebDriverWait(driver, 10).until(
#                 EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
#             )
# # 执行单击操作
# driver.execute_script("arguments[0].click()", button7)
# time.sleep(5)
# driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
# time.sleep(5)
#
# button8 = WebDriverWait(driver, 10).until(
#                 EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
#             )
# # 执行单击操作
# driver.execute_script("arguments[0].click()", button8)
# time.sleep(5)
# driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
# time.sleep(5)
# button9 = WebDriverWait(driver, 10).until(
#                 EC.presence_of_element_located((By.XPATH,'//*[@id="__next"]/div/div[7]/div/a/button'))
#             )
# # 执行单击操作
# driver.execute_script("arguments[0].click()", button9)
# time.sleep(5)
# driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
# time.sleep(5)

headers = {
    "Cookie": '_ALGOLIA=anonymous-3fb18e68-585c-4d7f-a322-25d5a7dbe6ce; preferredCountry=US; preferredLanguage=en; _cs_c=0; CookieConsent={stamp:%277cI74f6TnhgM+0anYxP/Bsx+epWIFagsBuv4MZ/eQ0U4gYRorNbAow==%27%2Cnecessary:true%2Cpreferences:true%2Cstatistics:true%2Cmarketing:true%2Cmethod:%27explicit%27%2Cver:1%2Cutc:1713761855425%2Cregion:%27us-06%27}; _gcl_au=1.1.113865216.1713761750; c65da092-7552-4b9d-9eba-63ec48a48b03=c65da092-7552-4b9d-9eba-63ec48a48b03; _fbp=fb.1.1713761750098.1836140912; __lt__cid=10625c67-7aa1-4502-aaf0-5a33727fd2d2; _fwb=79zSnZDkK3pApFHfynB8p2.1713761750498; _pin_unauth=dWlkPU5USm1aR0V5WVRFdFpUZ3haaTAwT0RNeExUbGhPR1l0T0RZNFpqVmlOR1E0TWpWbA; usid_dolcegabbana_us=2c10be4e-a08c-4bc3-9a33-be3b52e16bd0; dwanonymous_f2e6cc7ea56419bfd1f5a93d603d09a2=bckKkVkehJlesRwra2wWYYwKkX; _tt_enable_cookie=1; _ttp=8D961A8LpJJB7IRX64mTnQmy9HS; 2c10be4e-a08c-4bc3-9a33-be3b52e16bd0=2c10be4e-a08c-4bc3-9a33-be3b52e16bd0; _evga_bec5={%22uuid%22:%22eef66cfcbdca68c7%22}; _sfid_4952={%22anonymousId%22:%22eef66cfcbdca68c7%22%2C%22consents%22:[]}; _gid=GA1.2.1173484477.1713761759; _scid=2c195065-ca8e-40a9-9e4a-f14139db9208; _sctr=1%7C1713715200000; oid_dolcegabbana_us=f_ecom_bkdb_prd; cqcid=bckKkVkehJlesRwra2wWYYwKkX; cquid=||; dwsecuretoken_f2e6cc7ea56419bfd1f5a93d603d09a2=""; cc-sg_dolcegabbana_us=1; cc-nx-g_dolcegabbana_us=isZFMalv5TvQeohzNylE5N00x5J4EZJj3jo--KFminE; dwsid=vJKrb_SWNDvLhdVCBGTtPuV_JRm2BF8KV7StUeXTbJyF82d0oO2WGVgctagGHNBJrBUO0GObcydV57Cyg1kt0Q==; dwac_fb529d7b095ea541e5129e12e0=x3n3OriiTi8fh2s2SsNm2J6UeUz6MCUeg7Y%3D|dw-only|||USD|false|Europe%2FRome|true; sid=x3n3OriiTi8fh2s2SsNm2J6UeUz6MCUeg7Y; __cq_dnt=0; dw_dnt=0; token_dolcegabbana_us=token-dolcegabbana_us; cid_dolcegabbana_us=bckKkVkehJlesRwra2wWYYwKkX; wcs_bt=s_291344551710:1713768543; __lt__sid=276395b8-f5d29a95; _uetsid=97268660006411ef8f82bdd298d0204b; _uetvid=972680e0006411ef8998859de75f3fce; tfpsi=13e7d003-4d54-4554-a5e9-74d49065300a; _cs_mk_ga=0.36303164815078226_1713768545246; _cs_id=14e8e57a-2358-abc2-8fd1-2093508d1457.1713761746.2.1713768545.1713767814.1.1747925746134.1; _cs_s=4.0.0.1713770345264; firstCqcid=bckKkVkehJlesRwra2wWYYwKkX; _ga_2S6SQZ66CV=GS1.1.1713767818.2.1.1713768546.59.0.0; _ga=GA1.2.126281971.1713761747; _scid_r=2c195065-ca8e-40a9-9e4a-f14139db9208; inside-eu4=495116969-9f4f56d60f74b16d2a8c7e122f68fefb8e44b0c24f54d028b1dc2586c82a6ca7-0-0; RT="z=1&dm=dolcegabbana.com&si=b45b9e4a-f315-48d0-8911-3d169da0e917&ss=lvaljphm&sl=0&tt=0&bcn=%2F%2F17de4c0e.akstat.io%2F"',
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
}
img_detail2 = ["main", "rollover", "back", "alt1", "alt2", "alt3"]
file_path = r"D:\wendangDisk\riverisland"
for i in range(1, 3):
    element = driver.find_element(
        By.XPATH,
        '//*[@id="tabpane-4JBqa3M2ZU8zevXT1HRvfv"]/div/div/div[2]/div/div[1]/div[{}]/div/div[2]/div/div[2]/div/div[2]/div[2]/div[1]/div[1]/a/picture/img'.format(
            i
        ),
    )
    href_value = element.get_attribute("src")
    log.info(href_value)
    element2 = driver.find_element(
        By.XPATH,
        '//*[@id="tabpane-4JBqa3M2ZU8zevXT1HRvfv"]/div/div/div[2]/div/div[1]/div[{}]/div/div[5]/div[1]/div/a/h2'.format(
            i
        ),
    )
    img_name = element.get_attribute("text")
    # for i in range(0,5):
    #     try:
    #
    log.info(img_name)
    # img_name1 = img_name.split('$')[0]
    #
    # for img_detail in img_detail2:
    #     img_url = 'https://images.riverisland.com/image/upload/t_ProductImagePortraitLarge/{}_{}'.format(href_value, img_detail)
    #     # log.info(img_url)
    #     r = requests.get(url=img_url, headers=headers)
    #
    #     new_folder_name = img_name1
    #     # Full path of the new folder
    #     new_folder_path = os.path.join(file_path, new_folder_name)
    #     # Create the new folder if it doesn't exist
    #     if not os.path.exists(new_folder_path):
    #         os.makedirs(new_folder_path)
    #     img_name2 = new_folder_path + '/' + img_name1 + '_{}.jpg'.format(img_detail)
    #
    #     with open(img_name2, 'wb') as f:
    #         f.write(r.content)
    #         log.info('{}下载完成'.format(img_name2))
