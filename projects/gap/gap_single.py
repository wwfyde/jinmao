import asyncio
import json
import random
from enum import Enum
from pathlib import Path

import httpx
import redis.asyncio as redis
from lxml import etree
from playwright.async_api import async_playwright, Playwright, Page, Route, BrowserContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from crawler import log
from crawler.config import settings
from crawler.db import engine
from crawler.models import Product
from crawler.store import save_sku_data, save_product_data, save_review_data

# urls = [
#     {
#         "women": [
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=0",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=1",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=2",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=3",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=4",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=5",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=6",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=7",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=8",
#         ]
#     },  # 女装 2804
#     {"men.all": "https://www.gap.com/browse/category.do?cid=1127944&department=75"},  # 男装 约1009
# ]
source = "gap"
sub_category = "default"  # 商品子类别
urls = [
    ("men", sub_category, "https://www.gap.com/browse/category.do?cid=1127944&department=75&pageId=0"),
    ("men", sub_category, "https://www.gap.com/browse/category.do?cid=1127944&department=75&pageId=1"),
    ("men", sub_category, "https://www.gap.com/browse/category.do?cid=1127944&department=75&pageId=2"),
    ("men", sub_category, "https://www.gap.com/browse/category.do?cid=1127944&department=75&pageId=3"),
    ("men", sub_category, "https://www.gap.com/browse/category.do?cid=1127944&department=75&pageId=4"),
]
# urls = [
#     # (
#     #     "women",
#     #     sub_category,
#     #     "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=0",
#     # ),
#     # (
#     #     "women",
#     #     sub_category,
#     #     "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=1",
#     # ),
#     # (
#     #     "women",
#     #     sub_category,
#     #     "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=2",
#     # ),
#     # (
#     #     "women",
#     #     sub_category,
#     #     "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=3",
#     # ),
#     # (
#     #     "women",
#     #     sub_category,
#     #     "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=4",
#     # ),
#     (
#         "women",
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=5",
#     ),
#     (
#         "women",
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=6",
#     ),
#     (
#         "women",
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=7",
#     ),
#     (
#         "women",
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=8",
#     ),
# ]
# primary_category = "boys"  # 商品主类别
# sub_category = "default"  # 商品子类别
# urls = [("boys", "default", "https://www.gap.com/browse/category.do?cid=6189&department=16")]
PLAYWRIGHT_TIMEOUT: int = settings.playwright.timeout or 1000 * 60
print(PLAYWRIGHT_TIMEOUT)
PLAYWRIGHT_CONCURRENCY: int = settings.playwright.concurrency or 10
PLAYWRIGHT_CONCURRENCY: int = 1
PLAYWRIGHT_HEADLESS: bool = settings.playwright.headless
# PLAYWRIGHT_HEADLESS: bool = True

__doc__ = """
    金茂爬虫, 主要通过按类别爬取和按搜索爬取两种方式
"""


class Category(Enum):
    girls = "14417"


# 这个函数负责启动一个浏览器，打开一个新页面，并在页面上执行操作。
# 它接受一个Playwright对象作为参数。


def get_product_id(url: str) -> str:
    parsed_url = httpx.URL(url)
    return parsed_url.params.get("pid")[:-3]


async def run(playwright: Playwright, urls: list[tuple]) -> None:
    # 从playwright对象中获取chromium浏览器
    chromium = playwright.chromium
    # 指定代理
    # proxy = {"server": "http://127.0.0.1:7890"}
    # 启动chromium浏览器，开启开发者工具，非无头模式
    # browser = await chromium.launch(headless=False, devtools=True)
    user_data_dir = settings.user_data_dir
    if settings.save_login_state:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir,
            headless=PLAYWRIGHT_HEADLESS,
            # headless=False,
            # slow_mo=50,  # 每个操作的延迟时间（毫秒），便于调试
            args=["--start-maximized"],  # 启动时最大化窗口
            # ignore_https_errors=True,  # 忽略HTTPS错误
            # devtools=True,  # 打开开发者工具
        )
    else:
        browser = await chromium.launch(headless=True, devtools=True)
        context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(settings.playwright.timeout)
    # 创建一个新的浏览器上下文，设置视口大小
    # context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    # 在浏览器上下文中打开一个新页面

    # 并发抓取商品
    semaphore = asyncio.Semaphore(PLAYWRIGHT_CONCURRENCY)  # 设置并发请求数限制为10
    log.debug(f"并发请求数: {PLAYWRIGHT_CONCURRENCY}")
    tasks = []
    # TODO 修改此处参数
    sku_index = [("814639", "814639002")]
    sku_ids = [
        "545906002",
        "883550062",
        "409146032",
        "500584012",
        "508982002",
        "438023002",
        "411679012",
        "568218182",
        "431842002",
        "416638062",
        "260636432",
        "403540002",
        "728863002",
        "871386002",
        "1000185002",
        "869730052",
        "869726132",
        "558957002",
        "855967032",
        "356168652",
        "871336002",
        "729618122",
        "821866002",
        "880266022",
        "540687002",
        "568217092",
        "880878002",
        "875081002",
        "563012002",
        "869722092",
        "260230112",
        "406725002",
        "794579002",
        "803567002",
        "570868002",
        "1000191002",
        "429165002",
        "660018002",
        "1000187002",
        "448087002",
        "474285002",
        "479461042",
        "794965092",
        "821325052",
        "431253002",
        "407881002",
        "407882002",
        "431248002",
        "431256002",
        "563335002",
        "563007002",
        "562984002",
        "655107002",
        "373509102",
        "729652002",
        "670538042",
        "664665002",
        "586769012",
        "586732002",
        "576561002",
        "536721012",
        "870589022",
        "854755022",
        "890601042",
        "890842002",
        "871357002",
        "855745002",
        "855025002",
        "857632002",
        "905272032",
        "869732002",
        "890860002",
        "729783002",
        "885257002",
        "871372002",
        "464373002",
        "855965012",
        "429014002",
        "540610002",
        "592037022",
        "540609002",
        "523562052",
        "834853112",
        "260277012",
        "873269002",
        "848883292",
        "447979002",
        "659618002",
        "871510002",
        "540613002",
        "540615042",
        "841725002",
        "586039002",
        "431159002",
        "585582012",
        "1000130002",
        "857615012",
        "480071002",
        "889933002",
        "876107042",
        "803528002",
        "857272002",
        "871438002",
        "763097042",
        "790890012",
        "873500002",
        "853476002",
        "891995002",
        "540664002",
        "885270012",
        "755814342",
        "586063002",
        "870580002",
        "661059042",
        "871390002",
        "1000184002",
        "1000186002",
        "855189012",
        "592231052",
        "855740002",
        "558870002",
        "711766002",
        "431230002",
        "883001002",
        "504521002",
        "562295002",
        "410052002",
        "409151002",
        "871323002",
        "873266002",
        "857646002",
        "432356012",
        "806999002",
        "409154102",
        "873616002",
        "749402002",
        "1000189002",
        "1000196002",
        "558943002",
        "558851002",
        "871509002",
        "853453002",
        "855181002",
        "570975002",
        "1000193002",
        "1000195002",
        "474278002",
        "474300002",
        "475858002",
        "448029002",
        "1000135002",
        "1000136002",
        "468180002",
        "467557002",
        "443611002",
        "558861002",
        "562980002",
        "562999002",
        "563004002",
        "562982002",
        "469007002",
        "539614072",
        "569554002",
        "855193002",
        "854731022",
        "869173002",
        "563344002",
        "563377002",
        "875076002",
        "790919002",
        "870565002",
        "810502002",
        "729367012",
        "866810022",
        "838328002",
        "892218002",
        "885267002",
        "883004002",
        "884446002",
        "884441002",
        "882985002",
        "431601002",
        "871493002",
        "873397002",
        "464370002",
        "756653002",
        "570424002",
        "665864002",
        "882138002",
        "523563052",
        "891557002",
        "570479002",
        "873496002",
        "854613002",
        "852795002",
        "802546112",
        "570098002",
        "586765002",
        "772532002",
        "406849002",
        "853466002",
        "977167012",
        "570471002",
        "484999002",
        "803547002",
        "875997002",
        "860146032",
        "853455002",
        "857259002",
        "703503002",
        "853367002",
        "728757002",
        "571079002",
        "725276002",
        "817987002",
        "474292002",
        "1000194002",
        "448104002",
        "1000139002",
        "448163002",
        "438382002",
        "467558002",
        "431194002",
        "563359002",
        "562986002",
        "563002002",
        "563028002",
        "570930002",
        "514109012",
        "409147012",
        "586767002",
        "876171042",
        "875131002",
        "821307032",
        "607068022",
        "885306002",
        "790823002",
        "728756002",
        "801175082",
        "586771012",
        "570657032",
        "880359002",
        "870049002",
        "508797002",
        "870045002",
        "870308012",
        "891308002",
        "433077002",
        "484774002",
        "538544002",
        "703536002",
        "767285112",
        "853484002",
        "431270002",
        "607134002",
        "853372002",
        "852810002",
        "871457002",
        "853472002",
        "416427002",
        "615913002",
        "451501022",
        "431236002",
        "853457002",
        "541190062",
        "1169518002",
        "1169504002",
        "448066002",
        "571390002",
        "564498002",
        "475981002",
        "521943002",
        "479573002",
        "664970012",
        "409122022",
        "742352002",
        "721402002",
        "876170002",
        "876173002",
        "872134002",
        "872139002",
        "803676002",
        "876183002",
        "876282002",
        "876278002",
        "404582032",
        "708566012",
        "795299002",
        "729770002",
        "810824012",
        "708824052",
        "565000012",
        "880336012",
        "706814022",
        "540641002",
        "513541002",
        "876046002",
        "771691022",
        "825962012",
        "825968052",
        "819065042",
        "754014012",
        "851358002",
        "876195002",
        "736395022",
        "851299002",
        "745051012",
        "1169505002",
        "1169506002",
        "1169503002",
        "1169502002",
        "728747002",
        "709931002",
        "876255002",
        "826477002",
        "876176002",
        "709337012",
        "876264002",
        "505871002",
        "742330022",
        "792265012",
        "866823002",
        "1000243002",
        "1000246002",
        "835830002",
        "569075002",
        "542723012",
        "542894002",
        "670622032",
        "601259002",
        "741321052",
        "753357002",
        "778551002",
        "778679002",
        "682533012",
        "851343002",
        "851357002",
        "876280002",
        "569147002",
        "750149002",
        "708564022",
        "797975002",
        "795303002",
        "542693122",
        "542783002",
        "662339022",
        "873614002",
        "876325002",
        "446507002",
        "586766002",
        "794580012",
        "818313002",
        "873494002",
        "409527012",
        "1000249002",
        "563005002",
        "880265002",
        "816860022",
        "416417002",
        "513506002",
        "463709032",
        "415800042",
        "231856572",
        "706808062",
        "664974002",
        "790822002",
        "816857002",
        "795344012",
        "795398032",
        "857725002",
        "824315022",
        "823165002",
        "823673002",
        "684836022",
        "814639002",
        "795345022",
    ]
    products = [
        "795346",
        "883550",
        "409146",
        "500584",
        "508982",
        "438023",
        "411679",
        "568218",
        "431842",
        "416638",
        "260636",
        "403540",
        "818866",
        "794565",
        "558802",
        "421104",
        "421102",
        "558957",
        "855967",
        "356168",
        "871336",
        "729618",
        "821866",
        "880266",
        "540687",
        "568217",
        "880878",
        "875081",
        "563012",
        "421103",
        "260230",
        "406725",
        "794579",
        "852814",
        "570868",
        "558758",
        "892217",
        "660034",
        "562241",
        "448087",
        "474285",
        "479461",
        "794965",
        "821325",
        "431253",
        "407881",
        "407882",
        "431248",
        "431256",
        "563335",
        "563007",
        "562984",
        "655107",
        "373509",
        "729652",
        "670538",
        "664665",
        "586769",
        "586732",
        "576561",
        "536721",
        "870589",
        "854755",
        "890601",
        "890842",
        "871357",
        "855745",
        "855025",
        "857632",
        "905272",
        "869732",
        "890860",
        "729783",
        "885257",
        "871372",
        "464373",
        "855965",
        "429014",
        "540610",
        "592037",
        "540609",
        "523562",
        "834853",
        "260277",
        "873269",
        "848883",
        "447979",
        "659618",
        "871510",
        "540613",
        "540615",
        "841725",
        "586039",
        "431159",
        "585582",
        "1000130",
        "857615",
        "480071",
        "889933",
        "876107",
        "803528",
        "857272",
        "871438",
        "763097",
        "790890",
        "873500",
        "853476",
        "891995",
        "540664",
        "885270",
        "755814",
        "586063",
        "870580",
        "661059",
        "871390",
        "1000184",
        "1000186",
        "855189",
        "592231",
        "855740",
        "558870",
        "711766",
        "431230",
        "883001",
        "504521",
        "562295",
        "410052",
        "409151",
        "871323",
        "873266",
        "857646",
        "432356",
        "806999",
        "409154",
        "873616",
        "749402",
        "1000189",
        "1000183",
        "558943",
        "559065",
        "794603",
        "570897",
        "855181",
        "703551",
        "1000193",
        "1000195",
        "474278",
        "474300",
        "475858",
        "448029",
        "1000135",
        "1000136",
        "468180",
        "467557",
        "443611",
        "558861",
        "562980",
        "562999",
        "563004",
        "562982",
        "469007",
        "539614",
        "569554",
        "855193",
        "854731",
        "869173",
        "563344",
        "563377",
        "875076",
        "790919",
        "870565",
        "810502",
        "729367",
        "866810",
        "838328",
        "892218",
        "885267",
        "883004",
        "884446",
        "884441",
        "882985",
        "431601",
        "871493",
        "873397",
        "464370",
        "756653",
        "570424",
        "665864",
        "882138",
        "523563",
        "891557",
        "570479",
        "873496",
        "854613",
        "852795",
        "802546",
        "570098",
        "586765",
        "772532",
        "406849",
        "853466",
        "977167",
        "570471",
        "484999",
        "803547",
        "875997",
        "860146",
        "853455",
        "857259",
        "703505",
        "853477",
        "728757",
        "795399",
        "570955",
        "817987",
        "474292",
        "1000194",
        "448104",
        "1000139",
        "448163",
        "438382",
        "467558",
        "431194",
        "563359",
        "562986",
        "563002",
        "563028",
        "570930",
        "514109",
        "409147",
        "586767",
        "876171",
        "875131",
        "821307",
        "607068",
        "885306",
        "790823",
        "728756",
        "801175",
        "586771",
        "570657",
        "880359",
        "870049",
        "508797",
        "870045",
        "870308",
        "891308",
        "433077",
        "484774",
        "538544",
        "703536",
        "767285",
        "853484",
        "431270",
        "607134",
        "853372",
        "852810",
        "871457",
        "853472",
        "416427",
        "615913",
        "451501",
        "431236",
        "853457",
        "541190",
        "1169518",
        "1169504",
        "448066",
        "571390",
        "564498",
        "475981",
        "521943",
        "479573",
        "664970",
        "409122",
        "742352",
        "721402",
        "876170",
        "876173",
        "872134",
        "872139",
        "803676",
        "876183",
        "876282",
        "876278",
        "404582",
        "708566",
        "795299",
        "729770",
        "810824",
        "708824",
        "565000",
        "880336",
        "706814",
        "540641",
        "513541",
        "876046",
        "771691",
        "825962",
        "825968",
        "819065",
        "754014",
        "851358",
        "876195",
        "736395",
        "851299",
        "745051",
        "1169505",
        "1169506",
        "1169503",
        "1169502",
        "728747",
        "709931",
        "876255",
        "826477",
        "876176",
        "709337",
        "876264",
        "505871",
        "742330",
        "792265",
        "866823",
        "1000245",
        "1000090",
        "798281",
        "569075",
        "542723",
        "542894",
        "670622",
        "601259",
        "741321",
        "753357",
        "778551",
        "778679",
        "682533",
        "851343",
        "851357",
        "876280",
        "569147",
        "750149",
        "708564",
        "797975",
        "795303",
        "542693",
        "542783",
        "662339",
        "873614",
        "876325",
        "446507",
        "586766",
        "794580",
        "818313",
        "873494",
        "409527",
        "1000249",
        "563005",
        "880265",
        "816860",
        "416417",
        "513506",
        "463709",
        "415800",
        "231856",
        "706808",
        "664974",
        "790822",
        "816857",
        "795344",
        "795398",
        "857725",
        "824315",
        "823165",
        "823673",
        "684836",
        "814639",
        "795345",
    ]
    sku_index = zip(products, sku_ids)
    sku_index = [("440866002", "440866")]
    products = [
        "831714",
        "876972",
        "891210",
        "733481",
        "876899",
        "701485",
        "669887",
        "735905",
        "595342",
        "858571",
        "1169556",
        "564645",
    ]
    sku_ids = [
        "831714132",
        "876974002",
        "891210002",
        "733481192",
        "876899012",
        "701485162",
        "669887222",
        "735905112",
        "595342002",
        "858571032",
        "1169556002",
        "564645002",
    ]
    sku_index = zip(products, sku_ids)
    primary_category = "boys"
    sub_category = "default"
    for product_id, sku_id in sku_index:
        tasks.append(
            open_pdp_page(
                context,
                semaphore,
                product_id,
                sku_id,
                primary_category=primary_category,
                sub_category=sub_category,
                source=source,
            )
        )

    result = await asyncio.gather(*tasks)
    log.info(f"获取到的商品sku_id 列表: {result}")

    # break
    # 商品摘取完毕
    # 关闭浏览器context
    log.info("商品抓取完毕, 关闭浏览器")
    await context.close()


async def open_pdp_page(
    context: BrowserContext,
    semaphore: asyncio.Semaphore,
    product_id: str,
    sku_id: str,
    *,
    source: str,
    primary_category: str,
    sub_category: str,
):
    async with semaphore:
        # product_detail_page 产品详情页
        pdp_url = f"https://www.gap.com/browse/product.do?pid={sku_id}#pdp-page-content"

        # sku_id = int(httpx.URL(pdp_url).params.get("pid", 0))
        log.info(f"{sku_id=}")
        # 检查商品是否已抓取过
        r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
        async with r:
            result = await r.get(f"status:{source}:{primary_category}:{sub_category}:{product_id}:{sku_id}")
            log.info(f"商品{product_id}, sku:{sku_id}, redis抓取状态标记: {result=}")
            if result == "done":
                log.warning(f"商品{product_id=}, {sku_id=}已抓取过, 跳过")
                return sku_id
        sub_page = await context.new_page()
        sub_page.set_default_timeout(PLAYWRIGHT_TIMEOUT)

        async with sub_page:
            # await sub_page.goto(pdp_url)
            log.warning("当前未拦截图像")
            # await sub_page.route(
            #     "**/*",
            #     lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
            # )
            review_status = None
            route_event = asyncio.Event()

            async def handle_route(route: Route):
                """
                拦截评论路由并获取评论信息
                """
                request = route.request

                if "/reviews" in request.url:
                    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                    result = None
                    async with r:
                        result = await r.get(f"review_status:{source}:{primary_category}:{sub_category}:{product_id}")
                        log.info(f"商品评论: {product_id} 评论, redis状态标记: {result=}")
                        if result == "done":
                            log.warning(f"商品评论{product_id=}已抓取过, 跳过")

                    if result is None:
                        log.info(f"当前评论还未抓取: {request.url}")
                        response = await route.fetch()
                        json_dict = await response.json()
                        # 将评论信息保存到文件 注意分页

                        product_raw_dir = settings.data_dir.joinpath(
                            source, primary_category, sub_category, product_id, "raw_data"
                        )
                        product_raw_dir.mkdir(parents=True, exist_ok=True)

                        with open(f"{product_raw_dir}/review-{product_id}-00.json", "w") as f:
                            f.write(json.dumps(json_dict, indent=4, ensure_ascii=False))

                        # TODO  获取评论信息
                        reviews, total_count = parse_reviews_from_api(json_dict)
                        log.info(f"预期评论数{total_count}, {len(reviews)}")
                        page_size = 25
                        total_pages = (total_count + page_size - 1) // page_size
                        log.info(f"总页数{total_pages}")

                        semaphore = asyncio.Semaphore(10)  # 设置并发请求数限制为5
                        tasks = []
                        for i in range(1, total_pages + 1):
                            review_url = (
                                request.url
                                + "&sort=Newest"
                                + f"&paging.from={10 + (i - 1) * page_size}"
                                + f"&paging.size={page_size}"
                                + "&filters=&search=&sort=Newest&image_only=false"
                            )
                            tasks.append(
                                fetch_reviews(
                                    semaphore,
                                    review_url,
                                    request.headers,
                                    product_id=product_id,
                                    index=i,
                                    primary_category=primary_category,
                                    sub_category=sub_category,
                                )
                            )

                        new_reviews = await asyncio.gather(*tasks)
                        nonlocal review_status
                        for review in new_reviews:
                            if review is not None:
                                reviews.extend(review)
                            else:
                                review_status = "failed"
                                log.warning(f"评论获取失败: {review}")

                        log.info(f"实际评论数{len(reviews)}")
                        # 存储评论信息
                        product_store_dir = settings.data_dir.joinpath(
                            source, primary_category, sub_category, product_id
                        )
                        product_store_dir.mkdir(parents=True, exist_ok=True)
                        with open(f"{product_store_dir}/review-{product_id}.json", "w") as f:
                            log.info(f"存储评论到文件{product_store_dir}/review-{product_id}.json")
                            f.write(json.dumps(reviews, indent=4, ensure_ascii=False))
                        # 将评论保存到数据库

                        save_review_data(reviews)
                        # log.warning("当前使用批量插入评论方式!")
                        # save_review_data_bulk(reviews)
                        if review_status == "failed":
                            log.warning(f"商品评论{product_id}抓取失败, 标记redis状态为  failed ")
                            r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                            async with r:
                                await r.set(
                                    f"review_status:{source}:{primary_category}:{sub_category}:{product_id}", "failed"
                                )

                        else:
                            r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                            async with r:
                                log.info(f"商品评论{product_id}抓取完毕, 标记redis状态")
                                await r.set(
                                    f"review_status:{source}:{primary_category}:{sub_category}:{product_id}", "done"
                                )
                        # # 聚合评论
                        # product_store_dir2 = settings.data_dir.joinpath(source, "reviews")
                        # product_store_dir2.mkdir(parents=True, exist_ok=True)
                        # with open(f"{product_store_dir2}/review-{product_id}.json", "w") as f:
                        #     log.info(f"存储评论到文件{product_store_dir}/review-{product_id}.json")
                        #     f.write(json.dumps(reviews, indent=4, ensure_ascii=False))
                        route_event.set()
                        # log.info("获取评论信息")
                        # with open(f"{settings.project_dir.joinpath('data', 'product_info')}/data-.json", "w") as f:
                        #     f.write(json.dumps(json_dict))
                        # pass
                    else:
                        route_event.set()
                # if "api" in request.pdp_url or "service" in request.pdp_url:
                #
                #     log.info(f"API Request URL: {request.pdp_url}")
                await route.continue_()

            await sub_page.route("**/display.powerreviews.com/**", handle_route)

            # 进入新页面

            await sub_page.goto(pdp_url, timeout=PLAYWRIGHT_TIMEOUT)
            log.info(f"进入商品页面: {pdp_url}")

            # sub_page.on("request", lambda request: log.info(f"Request: {request.pdp_url}"))
            # sub_page.on("response", lambda response: log.info(f"Request: {response.pdp_url}"))

            # 拦截所有api pdp_url
            await sub_page.wait_for_timeout(5 * 1000)
            scroll_pause_time = random.randrange(1500, 2500, 500)
            await scroll_page(sub_page, scroll_pause_time=scroll_pause_time)
            # await scroll_to_bottom_v1(sub_page)
            await sub_page.wait_for_timeout(3000)
            await sub_page.wait_for_load_state()
            content = await sub_page.content()
            raw_data_dir = settings.data_dir.joinpath(source, primary_category, sub_category, product_id, "raw_data")
            raw_data_dir.mkdir(parents=True, exist_ok=True)
            with open(f"{raw_data_dir}/pdp-{product_id}.html", "w") as f:
                f.write(content)
            # 获取产品详情页(pdp)信息
            dom_pdp_info = await parse_sku_from_dom_content(
                content, product_id=product_id, sku_id=str(sku_id), source=source, product_url=pdp_url
            )
            # TODO 更新信息到数据库和json文件 或者等从接口拿取后统一写入
            model_image_urls = dom_pdp_info.get("model_image_urls", [])
            log.debug(f"从 dom中解析到的图片列表{model_image_urls=}")
            r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
            async with r:
                image_status = await r.get(
                    f"image_download_status:{source}:{primary_category}:{sub_category}:{product_id}:{sku_id}"
                )
                if image_status == "done":
                    log.warning(f"商品: {product_id}, sku:{sku_id}, 图片下载状态: {image_status}, 跳过")
                else:
                    base_url = "https://www.gap.com"
                    image_tasks = []
                    semaphore = asyncio.Semaphore(10)  # 设置并发请求数限制为10
                    sku_dir = settings.data_dir.joinpath(
                        source, primary_category, sub_category, str(product_id), str(sku_id)
                    )
                    sku_model_dir = sku_dir.joinpath("model")
                    sku_model_dir.mkdir(parents=True, exist_ok=True)
                    for index, url in enumerate(model_image_urls):
                        url = url.replace("https://www.gap.com", "")
                        image_tasks.append(
                            fetch_images(
                                semaphore,
                                base_url + url,
                                {},
                                file_path=sku_model_dir.joinpath(f"model-{(index + 1):02d}-{url.split('/')[-1]}"),
                            )
                        )

                    image_download_status = await asyncio.gather(*image_tasks)
                    if all(image_download_status) and len(image_download_status) > 0:
                        r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                        async with r:
                            await r.set(
                                f"image_download_status:{source}:{primary_category}:{sub_category}:{product_id}:{sku_id}",
                                "done",
                            )
                            log.warning(f"商品图片: {product_id}, sku:{sku_id}, 图片下载完成, 标记状态为done")
                    else:
                        log.warning(f"商品图片: {product_id}, sku:{sku_id}, 图片下载失败, 标记为failed")
                        r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                        async with r:
                            await r.set(
                                f"image_download_status:{source}:{primary_category}:{sub_category}:{product_id}:{sku_id}",
                                "failed",
                            )
                        log.warning("商品图片抓取失败")
                        return sku_id

            # await sub_page.get_by_label("close email sign up modal").click()
            await sub_page.wait_for_load_state("domcontentloaded")
            # await sub_page.wait_for_timeout(60000)
            # await sub_page.wait_for_selector("h1")

            await route_event.wait()
            log.info(f"商品[product]: {product_id}评论抓取完毕, 抓取状态: {review_status}")
            if review_status == "failed":
                log.warning(f"商品评论{product_id}抓取失败, 跳过")
                return sku_id
            log.debug("路由执行完毕")
            await asyncio.sleep(random.randrange(1, 8, 3))
        # 返回sku_id 以标记任务成功
        log.info(f"任务完成: {product_id=}, {sku_id=}")
        r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
        async with r:
            log.info(f"商品{product_id=}, {sku_id=}抓取完毕, 标记redis状态")
            await r.set(f"status:{source}:{primary_category}:{sub_category}:{product_id}:{sku_id}", "done")
        return sku_id


async def parse_sku_from_api(sku: dict, sku_id: int) -> dict | None:
    """
    获取商品信息
    """
    # to
    pdm_item: dict | None = sku.get("pdp_item", None)
    if not pdm_item:
        return None
    category = sku.get("pdp_item", "")
    sku_url: str = pdm_item.get("item_url")
    if sku_url:
        sku_id = httpx.URL(sku_url).params.get("pid", "")
    else:
        sku_id = None
    product_id = pdm_item.get("uni").split("||")[0]
    image_url = pdm_item.get("image_url")
    images: list = pdm_item.get("details").get("original_images") if pdm_item.get("details") else None
    title = pdm_item.get("title")

    return dict(
        sku_id=sku_id,
        product_id=product_id,
        category=category,
        sku_url=sku_url,
        image_url=image_url,
        image_url_outer=image_url,
        title=title,
        images=images,
    )


async def parse_sku_from_dom_content(
    content: str, *, product_id: str, sku_id: str, source: str, product_url: str
) -> dict:
    """
    解析页面内容
    """
    tree = etree.HTML(content)

    # 获取商品名称
    product_name_node = tree.xpath('//*[@id="buy-box"]/div/h1/text()')
    product_name = product_name_node[0] if product_name_node else None
    log.info(f"{product_name=}")

    # 获取价格
    price_node = tree.xpath('//*[@id="buy-box"]/div/div/div[1]/div[1]/span/text()')
    price = price_node[0] if price_node else None

    log.info(f"{price=}")
    # 原价抓取存在问题, 可能是价格区间
    # original_price = tree.xpath("//*[@id='buy-box']/div/div/div[1]/div[1]/div/span/text()")[0]
    # log.info(original_price)

    # 获取颜色
    color_node = tree.xpath('//*[@id="swatch-label--Color"]/span[2]/text()')
    color = color_node[0] if color_node else None
    log.info(f"{color=}")
    # fit_size 适合人群
    attributes = []
    fit_and_size = tree.xpath(
        "//*[@id='buy-box-wrapper-id']/div/div[2]/div/div/div/div[2]/div[1]/div/div[1]/div/div/ul/li/text()"
    )
    log.info(fit_and_size)
    attributes.extend(fit_and_size)
    # 产品详情
    product_details: list = tree.xpath(
        '//*[@id="buy-box-wrapper-id"]/div/div[2]/div/div/div/div[2]/div[2]/div/div[1]/div/ul/li/span/text()'
    )
    attributes.extend(product_details)
    log.info(product_details)
    # 面料
    fabric_and_care: list = tree.xpath(
        "//*[@id='buy-box-wrapper-id']/div/div[2]/div/div/div/div[2]/div[3]/div/div[1]/div/ul/li/span/text()"
    )
    attributes.extend(fabric_and_care)
    log.info(fabric_and_care)
    # TODO  下载 模特图片

    # model_image_urls_raw = tree.xpath("//*[@id="product"]/div[1]/div[1]/div[3]/div[2]/div/div/div[1]/div/div/div/div/div/div/a/@href")  # noqa

    # FIXME 模特图片
    # """#product > div.l--sticky-wrapper.pdp-mfe-wjfrns > div.l--breadcrumb-photo-wrapper.pdp-mfe-19rjz4o > div.product_photos-container > div.l--carousel.pdp-mfe-m9u4rn > div > div > div.product-photo.pdp-mfe-83e5v2 > div > div > div > div > div.slick-slide.slick-active.slick-current > div > a"""
    model_image_urls_raw = tree.xpath("//*[@id='product']/div[1]/div[1]/div[3]/div[2]/div/div/div/a/@href")
    # 旧款
    model_image_urls_raw2 = tree.xpath(
        "//*[@id='product']/div[1]/div[1]/div[3]/div[2]/div/div/div[1]/div/div/div/div/div/div/a/@href"
    )
    # """//*[@id="product"]/div[1]/div[1]/div[3]/div[2]/div/div/div[1]/div/div/div/div/div[3]/div/a"""
    model_image_urls = []
    model_image_urls_raw.extend(model_image_urls_raw2)
    for item in model_image_urls_raw:
        log.info(item)
        model_image_urls.append("https://www.gap.com" + item)
    # product_id = product_details[-1] if product_details else None
    if len(model_image_urls) > 0:
        model_image_url = model_image_urls[0]
        image_url = model_image_urls[-1]
    else:
        log.warning(f"当前商品:{product_id=}, {sku_id=}, 未获取到图片")
        model_image_url = None
        image_url = None

    pdp_info = dict(
        price=price,
        # original_price=original_price,
        product_name=product_name,
        color=color,
        fit_size=fit_and_size,
        product_details=product_details,
        fabric_and_care=fabric_and_care,
        product_id=product_id,
        sku_id=sku_id,
        sku_url=product_url,
        source=source,
        model_image_url=model_image_url,
        image_url=image_url,
        image_url_outer=image_url,
        model_image_urls=model_image_urls,
        attributes=attributes,
    )
    # 将从页面提取到的信息保存的数据库
    save_sku_data(pdp_info)
    with Session(engine) as session:
        stmt = select(Product.sku_id).where(Product.product_id == product_id, Product.source == source)

        product_sku_id = session.execute(stmt).scalar_one_or_none()
        if sku_id == product_sku_id:
            save_product_data(
                dict(
                    product_id=product_id,
                    attributes=attributes,
                    product_url=product_url,
                    source=source,
                    color=color,
                    image_url_outer=image_url,
                    fit_size=fit_and_size,
                    product_details=product_details,
                    fabric_and_care=fabric_and_care,
                )
            )
    return pdp_info


async def get_reviews_from_url_by_id(product_id: str):
    async with httpx.AsyncClient(timeout=settings.httpx_timeout) as client:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://www.gap.com",
        }
        url = f"https://display.powerreviews.com/m/1443032450/l/en_US/product/{product_id}/reviews?_noconfig=true"
        response = await client.get(url=url, headers=headers)
        log.info(response.text)
        return response.json()


async def scroll_to_bottom_v1(page: Page):
    # 获取页面的高度
    log.debug("尝试页面滚动")

    previous_height = await page.evaluate("document.body.scrollHeight")
    while True:
        # 滚动到页面底部

        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        # 等待页面加载新内容
        await page.wait_for_timeout(random.randrange(1000, 3500, 500))  # 等待 4~8 秒
        # 获取新的页面高度
        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == previous_height:
            log.debug("页面滚动完毕")
            break
        previous_height = new_height


async def scroll_to_bottom(page: Page, scroll_pause_time: int = 1000, max_scroll_attempts: int = 20):
    """
    滚动页面到底部，以加载所有动态内容。

    :param page: Playwright页面对象
    :param scroll_pause_time: 每次滚动后等待的时间（毫秒）
    :param max_scroll_attempts: 最大滚动次数
    """
    previous_height = await page.evaluate("document.body.scrollHeight")
    scroll_attempts = 0

    while scroll_attempts < max_scroll_attempts:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(scroll_pause_time)

        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == previous_height:
            break
        previous_height = new_height
        scroll_attempts += 1

    if scroll_attempts >= max_scroll_attempts:
        log.info("Reached maximum scroll attempts")
    else:
        log.info(f"Scrolled to bottom after {scroll_attempts} attempts")


async def scroll_page(page: Page, scroll_pause_time: int = 1000, max_times: int = 30):
    viewport_height = await page.evaluate("window.innerHeight")
    log.debug("尝试滚动页面")
    i = 0
    current_scroll_position = 0
    while True:
        # 滚动视口高度
        i += 1
        # log.info(f"第{i}次滚动, 滚动高度: {viewport_height}")
        current_scroll_position += viewport_height
        # log.info(f"当前滚动位置: {current_scroll_position}")
        # 滚动到新的位置
        await page.evaluate(f"window.scrollTo(0, {current_scroll_position})")
        # 滚动到页面底部
        # await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(scroll_pause_time / 1000)
        # await page.wait_for_timeout(scroll_pause_time)
        await page.wait_for_load_state("domcontentloaded")
        # 重新获取页面高度
        scroll_height = await page.evaluate("document.body.scrollHeight")
        # 获取当前视口位置
        current_viewport_position = await page.evaluate("window.scrollY + window.innerHeight")
        # log.info(f"页面高度: {scroll_height}")
        # log.info(f"当前视口位置: {current_viewport_position}")

        if current_viewport_position >= scroll_height or current_scroll_position >= scroll_height:
            log.debug("滚动到底部")
            break
        if i >= max_times:
            log.warning(f"超过最大滚动次数{max_times}")
            break
        # previous_height = new_height


async def parse_category_from_api(
    data: dict, page: Page, gender: str, *, source: str, primary_category: str, sub_category: str
):
    """
    解析类型页面的API接口
    """
    results = []
    products: list = data.get("products", [])
    product_count = int(data.get("totalColors", 0))
    category_skus = data.get("categories")[0]["ccList"]
    skus_index = [(item["styleId"], item["ccId"]) for item in category_skus]
    pagination = dict(
        current_page=data.get("pagination").get("currentPage") if data.get("pagination") else None,
        page_size=data.get("pagination").get("currentPage") if data.get("pagination") else None,
        total_pages=data.get("pagination").get("currentPage") if data.get("pagination") else None,
        total=data.get("totalColors"),
    )
    log.info(f"通过接口, 共发现{product_count}件商品")
    for product in products:
        # TODO 需要商品图片连接
        result = dict(
            product_id=product.get("styleId", None),  # 商品id
            product_name=product.get("styleName", None),  # 商品名称
            rating=product.get("reviewScore", None),  # 评分
            review_count=product.get("reviewCount", None),  # 评论数量
            rating_count=product.get("reviewCount", None),  # 评分数量
            type=product.get("webProductType", None),  # 商品类型
            category=product.get("webProductType", None),  # 商品类别
            released_at=product.get("releaseDate", None),  # 发布日期
            brand="gap",  # 品牌
            gender=gender,  # 性别
            source=source,  # 数据来源
        )

        skus = product.get("styleColors", [])
        # 将sku_id添加到product中
        if len(skus) > 0:
            result["sku_id"] = skus[0].get("ccId", None)
            images = skus[0].get("images", [])
            # for item in images:
            #     # 获取主图
            #     if item["type"] == "AV6_Z":
            #         result["image_url"] = "https://www.gap.com" + item.get("path") if item.get("path") else None
            #         continue
            #     if item["type"] == "Z":
            #         result["model_image_url"] = "https://www.gap.com" + item.get("path") if item.get("path") else None
            #     if item["type"] == "AV1_Z":
            #         result["_image_url"] = "https://www.gap.com" + item.get("path") if item.get("path") else None

            # 将图片上传到oss
            # 下载图片
            # FIXME
            # try:
            #     async with httpx.AsyncClient(timeout=15) as client:
            #         response = await client.get(result["image_url"] + "?q=h&w=322")
            #         image_bytes = response.content
            #         image_url_stored = upload_image(
            #             filename=result["image_url"].replace("https://www.gap.com/", ""),
            #             data=image_bytes,
            #             prefix=f"crawlers/{PROVIDER}",
            #         )
            #
            #         result["image_url_stored"] = image_url_stored
            # except Exception as exc:
            #     log.error(f"下载图片失败: {exc}")

        sub_results = []
        product_dir = settings.data_dir.joinpath(source, primary_category, sub_category, str(result["product_id"]))
        product_dir.mkdir(parents=True, exist_ok=True)
        for sku in skus:
            sub_result = dict(
                sku_id=sku.get("ccId", None),  # sku id
                product_id=product.get("styleId", None),  # 商品id
                product_name=product.get("styleName", None),  # 商品名称
                sku_name=sku.get("ccName", None),  # sku 名称
                color=sku.get("ccName", None),  # 颜色
                description=sku.get("ccShortDescription", None),  # sku 描述
                inventory=sku.get("inventoryCount", None),  # 库存
                size=None,
                inventory_status=sku.get("inventoryStatus", None),  # 库存状态
                vendor=sku.get("vendorName", None),  # 供应商
                source=source,
            )
            sub_results.append(sub_result)
            sku_dir = product_dir.joinpath(str(sub_result["sku_id"]))
            sku_dir.mkdir(parents=True, exist_ok=True)
            with open(f"{sku_dir}/sku.json", "w") as f:
                f.write(json.dumps(sub_result, indent=4, ensure_ascii=False))
        result["skus"] = sub_results
        # 保存SKU数据
        save_sku_data(sub_results)
        with open(
            f"{settings.data_dir.joinpath(source, primary_category, sub_category, str(result['product_id']))}/product.json",
            "w",
        ) as f:
            f.write(json.dumps(result, indent=4, ensure_ascii=False))
        results.append(result)
    # 保存商品数据
    save_product_data(results)

    return results, product_count, pagination, skus_index
    pass


def parse_reviews_from_api(review_data: dict) -> tuple[list[dict], int | None]:
    # 获取分页信息
    review_domain = "https://display.powerreviews.com"
    paging_raw = review_data.get("paging", {})
    total_count = paging_raw.get("total_results", None) if paging_raw else None
    current_page = paging_raw.get("current_page_number", None) if paging_raw else None
    total_results = paging_raw.get("total_results", None) if paging_raw else None
    total_pages = paging_raw.get("pages_total", None) if paging_raw else None

    # 获取评论
    reviews: list = review_data.get("results", [])[0].get("reviews", [])

    my_reviews = []

    for review in reviews:
        my_review = dict(
            review_id=review.get("review_id", None),
            proudct_name=review.get("details").get("product_name", None) if review.get("details") else None,
            title=review.get("details").get("headline", None) if review.get("details") else None,
            comment=review.get("details").get("comments", None) if review.get("details") else None,
            nickname=review.get("details").get("nickname", None) if review.get("details") else None,
            product_id=review.get("details").get("product_page_id", None) if review.get("details") else None,
            sku_id=review.get("details").get("product_variant", None) if review.get("details") else None,
            helpful_votes=review.get("metrics").get("helpful_votes", None) if review.get("metrics") else None,
            not_helpful_votes=review.get("metrics").get("not_helpful_votes", None) if review.get("metrics") else None,
            rating=review.get("metrics").get("rating", None) if review.get("metrics") else None,
            helpful_score=review.get("metrics").get("helpful_score", None) if review.get("metrics") else None,
            source=source,
        )
        my_reviews.append(my_review)
    return my_reviews, total_count


def get_cookies_from_playwright(cookies: dict) -> str:
    cookies_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
    return "; ".join([f"{key}={value}" for key, value in cookies_dict.items()])


async def fetch_reviews(
    semaphore,
    url,
    headers,
    product_id: str | None = None,
    index: int | None = None,
    *,
    primary_category: str,
    sub_category: str,
) -> list | None:
    async with semaphore:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()  # 检查HTTP请求是否成功
                json_dict = response.json()
                raw_review_data = settings.data_dir.joinpath(
                    source, primary_category, sub_category, product_id, "raw_data"
                )
                raw_review_data.mkdir(parents=True, exist_ok=True)
                with open(f"{raw_review_data}/review-{product_id}-{index:02d}.json", "w") as f:
                    f.write(json.dumps(json_dict, indent=4, ensure_ascii=False))
                return parse_reviews_from_api(json_dict)[0]
        except Exception as exc:
            log.error(f"获取评论失败, {exc}")
            return None


async def fetch_images(semaphore: asyncio.Semaphore, url, headers, file_path: Path | str) -> bool:
    async with semaphore:
        try:
            start_time = asyncio.get_event_loop().time()
            async with httpx.AsyncClient(timeout=60) as client:
                log.debug(f"下载图片: {url}")
                response = await client.get(url, headers=headers)
                response.raise_for_status()  # 检查HTTP请求是否成功
                image_bytes = response.content
                with open(f"{str(file_path)}", "wb") as f:
                    f.write(image_bytes)
            end_time = asyncio.get_event_loop().time()
            log.debug(f"下载图片耗时: {end_time - start_time:.2f}s")
            return True
        except Exception as exc:
            log.error(f"下载图片失败, {exc=}")
            return False


async def go_to_pdp_page(semapage: Page, pdp_url: str):
    # TODO  并发获取商品
    pass


# 这个函数是脚本的主入口点。
# 它创建一个playwright对象，并将其传递给run函数。
async def main():
    # 创建一个playwright对象并将其传递给run函数
    async with async_playwright() as p:
        await run(p, urls)
        ...


# 这是脚本的入口点。
# 它开始执行main函数。
if __name__ == "__main__":
    # 指定本地代理
    asyncio.run(main())
