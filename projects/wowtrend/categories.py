import asyncio
import json

import httpx
from fake_useragent import UserAgent
from playwright.async_api import Playwright, async_playwright, Route

from crawler import log
from crawler.config import settings
from projects.gap.gap import PLAYWRIGHT_HEADLESS

source = "target"
domain = "https://www.wow-trend.com"
PLAYWRIGHT_TIMEOUT = settings.playwright.timeout
PLAYWRIGHT_CONCURRENCY = settings.playwright.concurrency
PLAYWRIGHT_CONCURRENCY = 5
settings.save_login_state = True
download_image = False

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
        browser = await chromium.launch(
            headless=PLAYWRIGHT_HEADLESS,
            proxy=proxy,
            # devtools=True,
        )
        context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(settings.playwright.timeout)
    # context.set_default_timeout(60000)
    # 创建一个新的浏览器上下文，设置视口大小
    # context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    # 在浏览器上下文中打开一个新页面
    page = await context.new_page()

    async with page:
        # 打开新的页面
        # "https://apps01.wow-trend.com/api/trend/article/get-list?nav_id=16&gender_id=72105"
        # url = "https://www.wow-trend.com/column/?nav_id=16&gender_id=72105"

        url = "https://www.wow-trend.com/column/?nav_id=111&gender_id=72105&keywords=miu%20miu&mode1=成册"
        url = "https://www.wow-trend.com/column/?nav_id=111&gender_id=72105&keywords=chanel&mode1=%E6%88%90%E5%86%8C"
        url = "https://www.wow-trend.com/column/?nav_id=111&gender_id=72105&keywords=Celine&mode1=%E6%88%90%E5%86%8C"
        nav_id = httpx.URL(url).params.get("nav_id")
        gender_id = httpx.URL(url).params.get("gender_id")
        api_event = asyncio.Event()
        all_meetings = []
        total_meeting = 0
        # 拦截所有图片
        await page.route(
            "**/*",
            lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
        )

        async def handle_route(route: Route):
            request = route.request
            if "get-list" in request.url:
                log.info(
                    f"拦截产品详情页API: {route.request.url}",
                )
                # TODO 获取产品信息
                response = await route.fetch()
                json_dict = await response.json()
                pagination, meetings = await parse_api(resp=json_dict, nav_id=nav_id, gender_id=gender_id)
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
                        fetch_meetings(semaphore, url, headers=request.headers, nav_id=nav_id, gender_id=gender_id)
                    )
                extra_meetings = await asyncio.gather(*tasks)
                for extra_meeting in extra_meetings:
                    meetings.extend(extra_meeting)
                nonlocal all_meetings
                all_meetings = meetings
                with open("meetings_celine.json", "w") as f:
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
        await page.pause()


async def parse_api(resp: dict, nav_id: str, gender_id: str) -> tuple[dict, list]:
    url_path = f"{domain}/article/info/"

    if resp.get("status_code") == 200:
        data = resp.get("data")
        current_page = data.get("currentPage", 0)
        page_size = data.get("pageSize", 0)
        total = data.get("total", 0)
        total_page = data.get("totalPage", 0)
        pagination = dict(current_page=current_page, page_size=page_size, total=total, total_page=total_page)

        meeting_lists = data.get("list", []) if data else []
        meetings = []
        for meeting in meeting_lists:
            id = meeting.get("id")
            link = str(httpx.URL(url_path).copy_with(params=dict(id=id, nav_id=nav_id, gender_id=gender_id)))
            image_url = meeting.get("preview_picture")
            title = meeting.get("title")
            season = meeting.get("season_str")
            keywords = meeting.get("keywords", [])
            attr_data: dict = meeting.get("attr_data", {})
            meetings.append(
                dict(
                    id=id,
                    link=link,
                    image_url=image_url,
                    season=season,
                    title=title,
                    keywords=keywords,
                    attr_data=attr_data,
                    area=attr_data.get("area_name"),
                    menu=attr_data.get("menu_name"),
                )
            )
        return pagination, meetings
    else:
        log.error(f"接口返回错误code: {resp.get("status_code")}, message: {resp.get("message")}")


async def fetch_meetings(semaphore, url, headers, nav_id, gender_id):
    async with semaphore:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()  # 检查HTTP请求是否成功
            json_dict = response.json()
            return (await parse_api(json_dict, nav_id=nav_id, gender_id=gender_id))[-1]


async def main():
    # 创建一个playwright对象并将其传递给run函数
    async with async_playwright() as p:
        await run(p)
        ...


# 这是脚本的入口点。
# 它开始执行main函数。
if __name__ == "__main__":
    # 指定本地代理
    asyncio.run(main())
