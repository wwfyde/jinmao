import asyncio
import json
import logging
import sys
import time
from mimetypes import guess_extension
from pathlib import Path
import redis.asyncio as redis

import httpx
from fake_useragent import UserAgent
from playwright.async_api import Playwright, async_playwright, Route

from crawler.config import settings
from projects.gap.gap import PLAYWRIGHT_HEADLESS

source = "target"
domain = "https://www.wow-trend.com"
PLAYWRIGHT_TIMEOUT = settings.playwright.timeout
PLAYWRIGHT_CONCURRENCY = settings.playwright.concurrency
PLAYWRIGHT_CONCURRENCY = 6
settings.save_login_state = False
download_image = False
storage_path = Path.home().joinpath("wow-trend")
storage_path.mkdir(parents=True, exist_ok=True)


def initialize_logger(name: str, log_level: int = logging.INFO):
    """
    Initialize a logger with the specified name and log level.
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Create console handler with a higher log level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(log_level)

    # Create formatter and add it to the handler
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(filename)s - %(lineno)d - %(message)s")
    ch.setFormatter(formatter)

    # Add the handler to the logger
    if not logger.handlers:
        logger.addHandler(ch)

    return logger


log = initialize_logger(__name__, logging.DEBUG)
log.debug(f"将图像存储到目录{storage_path}")

ua = UserAgent(browsers=["edge", "chrome", "safari"])


async def run(playwright: Playwright) -> None:
    # 从playwright对象中获取chromium浏览器
    chromium = playwright.chromium
    # 指定代理
    # proxy = {"server": "http://127.0.0.1:7890"}
    # 启动chromium浏览器，开启开发者工具，非无头模式
    # browser = await chromium.launch(headless=False, devtools=True)
    proxy = {
        "server": settings.proxy_pool.server,
        "username": settings.proxy_pool.username,
        "password": settings.proxy_pool.password,
    }
    proxy = None
    user_data_dir = settings.user_data_dir
    if settings.save_login_state:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir,
            headless=PLAYWRIGHT_HEADLESS,
            proxy=proxy,
            # headless=False,
            # slow_mo=50,  # 每个操作的延迟时间（毫秒），便于调试
            # args=["--start-maximized"],  # 启动时最大化窗口
            # ignore_https_errors=True,  # 忽略HTTPS错误
            # devtools=True,  # 打开开发者工具
        )
    else:
        pass
    browser = await chromium.launch(
        headless=True,
        proxy=proxy,
        # devtools=True,
    )
    # context = await browser.new_context()

    # 设置全局超时

    # context.set_default_timeout(60000)
    # 创建一个新的浏览器上下文，设置视口大小
    # context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    # 在浏览器上下文中打开一个新页面

    # 从 文件中读取订货会列表
    with open("meetings-0704.json", "r", encoding="utf-8") as f:
        meetings: list[dict] = json.load(f)
    semaphore = asyncio.Semaphore(PLAYWRIGHT_CONCURRENCY)
    tasks = [process_meeting(browser, meeting, semaphore) for meeting in meetings]
    await asyncio.gather(*tasks)
    await browser.close()


async def process_meeting(browser, meeting, semaphore):
    async with semaphore:
        url = meeting.get("link")
        nav_id = httpx.URL(url).params.get("nav_id")
        gender_id = httpx.URL(url).params.get("gender_id")
        meeting_id = httpx.URL(url).params.get("id")
        log.debug(f"读取到订货会{meeting_id=}")
        api_event = asyncio.Event()
        all_meetings = []
        total_meeting = 0
        r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
        async with r:
            res = await r.get(f"wowtrend:2025chunxia:{meeting_id}")
            log.info(f"{meeting_id=}, 图片下载状态{res}")
            if res == "done":
                log.info("图片已下载, 跳过")
                return
        user_agent = ua.random
        context = await browser.new_context(user_agent=user_agent)
        # context = await browser.new_context()
        context.set_default_timeout(settings.playwright.timeout)

        await context.set_extra_http_headers(
            {
                "Cookie": "wowLoginToken=BearereyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczovL2FwcHMwMy53b3ctdHJlbmQuY29tL2FwaS9tZW1iZXIvcmVnaXN0ZXIiLCJpYXQiOjE3MjAwODU2NzUsImV4cCI6MTcyMDMwMTY3NSwibmJmIjoxNzIwMDg1Njc1LCJqdGkiOiJHendDS3ZNcFlrRTN0R2ZyIiwic3ViIjo0MjE4MjUsInBydiI6Ijg3ZTBhZjFlZjlmZDE1ODEyZmRlYzk3MTUzYTE0ZTBiMDQ3NTQ2YWEiLCJpcCI6IjEyNC45MC4xNjUuMTk0IiwiYmRnIjowLCJkZXYiOiIiLCJhcHBfZGV2aWNlX3N0ciI6IiIsImxvZ2lucyI6bnVsbCwib3BlbmlkIjoiIiwic2FsZXJfYXV0aCI6ZmFsc2UsInV1aWQiOiIiLCJzaW5nbGVfbG9naW4iOjB9.FPAvRXmPy1dAy5mi8ELzfmxXroXlns-fDS4JPw0_N-k",
                "Authorization": "BearereyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczovL2FwcHMwMy53b3ctdHJlbmQuY29tL2FwaS9tZW1iZXIvcmVnaXN0ZXIiLCJpYXQiOjE3MjAwODU2NzUsImV4cCI6MTcyMDMwMTY3NSwibmJmIjoxNzIwMDg1Njc1LCJqdGkiOiJHendDS3ZNcFlrRTN0R2ZyIiwic3ViIjo0MjE4MjUsInBydiI6Ijg3ZTBhZjFlZjlmZDE1ODEyZmRlYzk3MTUzYTE0ZTBiMDQ3NTQ2YWEiLCJpcCI6IjEyNC45MC4xNjUuMTk0IiwiYmRnIjowLCJkZXYiOiIiLCJhcHBfZGV2aWNlX3N0ciI6IiIsImxvZ2lucyI6bnVsbCwib3BlbmlkIjoiIiwic2FsZXJfYXV0aCI6ZmFsc2UsInV1aWQiOiIiLCJzaW5nbGVfbG9naW4iOjB9.FPAvRXmPy1dAy5mi8ELzfmxXroXlns-fDS4JPw0_N-k",
            }
        )
        page = await context.new_page()

        async with page:
            # 打开新的页面

            # 拦截所有图片
            await page.route(
                "**/*",
                lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
            )

            async def handle_route(route: Route):
                log.debug("拦截到api")
                request = route.request
                if "get-article-res" in request.url:
                    log.info(
                        f"拦截订货会页面API: {route.request.url}",
                    )
                    # TODO 获取产品信息
                    response = await route.fetch()
                    json_dict = await response.json()
                    pagination, meetings = await parse_api(
                        resp=json_dict, nav_id=nav_id, gender_id=gender_id, meeting_id=meeting_id
                    )
                    page_count = pagination.get("total_page")
                    nonlocal total_meeting
                    total_meeting = pagination.get("total")
                    print(json_dict)
                    # 按页码获取
                    tasks = []
                    for page_id in range(2, page_count + 1):
                        url = httpx.URL(request.url).copy_add_param("page", page_id)
                        semaphore = asyncio.Semaphore(5)
                        tasks.append(
                            fetch_images(
                                semaphore,
                                url,
                                headers=request.headers,
                                nav_id=nav_id,
                                gender_id=gender_id,
                                meeting_id=meeting_id,
                            )
                        )
                    extra_images = await asyncio.gather(*tasks)
                    for extra_meeting in extra_images:
                        meetings.extend(extra_meeting)
                    nonlocal all_meetings
                    all_meetings = meetings
                    with open("meetings.json", "w") as f:
                        f.write(json.dumps(meetings, ensure_ascii=False, indent=4))
                    api_event.set()
                await route.continue_()
                pass

            await page.route("**/api/trend/article/**", handle_route)

            await page.goto(url=url)
            # await page.goto("https://www.wow-trend.com/column/?nav_id=16&gender_id=72105&page=1&mode1=%E6%88%90%E5%86%8C")
            # await page.get_by_text("登录/注册").click()
            #
            # # 填写登录表单并提交
            # await page.get_by_placeholder("手机号/帐号").click()
            # await page.get_by_placeholder("手机号/帐号").fill("15700123731")
            # await page.get_by_placeholder("密码").fill("lemon.030613")
            # await page.get_by_role("button", name="登录").click()

            # 等待登录完成
            # await page.wait_for_timeout(5000)  # 等待5秒
            await page.wait_for_load_state()

            # 等待api 拦截执行完毕
            await api_event.wait()
            log.info(f"订货会url抓取完毕, 共{len(all_meetings)}条, 预期{total_meeting}条")
            # await page.pause()
            async with r:
                await r.set(f"wowtrend:2025chunxia:{meeting_id}", "done")
                log.info(f"订货会{meeting_id=}的图片下载完成")


async def parse_api(resp: dict, *, nav_id: str, gender_id: str, meeting_id: str) -> tuple[dict, list]:
    url_path = f"{domain}/article/info/"

    if resp.get("status_code") == 200:
        data = resp.get("data")
        current_page = data.get("currentPage", 0)
        page_size = data.get("pageSize", 0)
        total = data.get("total", 0)
        total_page = data.get("totalPage", 0)
        title = data.get("title", "")
        page_no = data.get("pageNo", 0)
        pagination = dict(current_page=current_page, page_size=page_size, total=total, total_page=total_page)

        images_list = data.get("resources", []) if data else []
        meetings = []
        for meeting in images_list:
            image_id = meeting.get("id")
            release_time = meeting.get("release_time")
            # link = str(httpx.URL(url_path).copy_with(params=dict(id=id, nav_id=nav_id, gender_id=gender_id)))
            image_url = meeting.get("hd_picture")
            preview_image_url = meeting.get("preview_picture")
            if image_url:
                download_url = image_url
            else:
                download_url = preview_image_url
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.get(download_url)
                    image_bytes = response.content
                    content_type = response.headers.get("Content-Type", "")
                    if content_type.startswith("image"):
                        # image_basename = image_basename.split(".")[0]
                        extension = guess_extension(content_type)
                        # log.info(f"图片类型{extension=}")
                    else:
                        log.warning("非图片类型!")
                        extension = ".jpg"
                    image_dir = storage_path.joinpath(f"{meeting_id}_{title}")
                    image_dir.mkdir(parents=True, exist_ok=True)
                    with open(f"{str(image_dir)}/{image_id}{extension}", "wb") as f:
                        f.write(image_bytes)
            except Exception:
                log.info(f"下载图片失败:跳过 {meeting_id=}, {image_id=}")

                # txt_lines = [f"image_id: {image_id}\n", f"title: {title}\n"]
                #
                # with open(f"{str(image_dir)}/{image_id}.txt", "w") as f:
                #     f.writelines(txt_lines)
            meetings.append(
                dict(
                    image_id=image_id,
                    # link=link,
                    image_url=image_url,
                    preview_image_url=preview_image_url,
                    title=title,
                )
            )
        return pagination, meetings
    else:
        log.error(f"接口返回错误code: {resp.get("status_code")}, message: {resp.get("message")}")


async def fetch_images(semaphore, url, headers, nav_id, gender_id, meeting_id):
    async with semaphore:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()  # 检查HTTP请求是否成功
            json_dict = response.json()
            return (await parse_api(json_dict, nav_id=nav_id, gender_id=gender_id, meeting_id=meeting_id))[-1]


async def main():
    # 创建一个playwright对象并将其传递给run函数
    i = 0
    while i < 50:
        i += 1
        try:
            async with async_playwright() as p:
                await run(p)
                ...
        except Exception as exc:
            log.warning(f"中断, 60s, 错误提示: {exc}")
        time.sleep(15)


# 这是脚本的入口点。
# 它开始执行main函数。
if __name__ == "__main__":
    # 指定本地代理
    asyncio.run(main())
