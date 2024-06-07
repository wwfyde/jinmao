import json
import uuid
from pathlib import Path

import httpx
import oss2
from fastapi import HTTPException
from playwright.async_api import Page

from crawler import log
from crawler.config import settings


async def simulate_user_scroll(page: Page):
    """
    模拟用户滚动
    """
    for _ in range(10):  # 滚动10次，每次滚动1000像素
        await page.mouse.wheel(0, 1000)
        await page.wait_for_timeout(1000)  # 等待页面加载新内容


async def scroll_to_bottom(page: Page):
    """
    通过JavaScript滚动到页面底部
    """
    previous_height = await page.evaluate("document.body.scrollHeight")
    while True:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000)  # 等待页面加载新内容
        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == previous_height:
            break
        previous_height = new_height


def save_to_json(data: dict, path: Path, filename: str):
    """
    保存数据到json文件
    """
    with open(path.joinpath(filename), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def upload_image(
    filename: str,
    data: str | bytes,
    prefix: str = "tmp",
    rename: bool = True,
    domain: str = None,
) -> str:
    """
    上传图片到OSS并返回其访问链接
    :param filename: 文件名
    :param data: 文件内容, 二进制数据或字符串
    :param prefix: OSS路径前缀 上传到OSS的路径
    :param rename: 是否重命名, 默认为True
    :param domain: OSS域名, 默认为None时使用bucket_name+endpoint
    """
    endpoint = settings.aliyun.end_point

    auth = oss2.Auth(settings.aliyun.access_key, settings.aliyun.secret_key)
    bucket_name = settings.aliyun.bucket_name
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    if rename:
        uid = uuid.uuid4()
        upload_file_name = f"{prefix}/{uid}.{filename.split('.')[-1]}"
    else:
        upload_file_name = f"{prefix}/{filename}"
    if prefix is None:
        # 临时文件, 使用OSS生命周期自动删除
        upload_file_name = f"tmp/{upload_file_name}"

    result = bucket.put_object(upload_file_name, data)
    domain = domain or settings.aliyun.domain
    if domain:
        image_link = f"https://{domain}/{upload_file_name}"
    else:
        image_link = f"https://{bucket_name}.{endpoint}/{upload_file_name}"
    if result.status == 200:
        return image_link
    else:
        raise HTTPException(status_code=result.status, detail=result.resp.read().decode())


async def scroll_page(
    page: Page,
    scroll_pause_time: int = 1000,
    max_attempt: int | None = None,
    source: str | None = None,
    page_size: int = 50,
):
    viewport_height = await page.evaluate("window.innerHeight")
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
        # await asyncio.sleep(scroll_pause_time / 1000)
        await page.wait_for_timeout(scroll_pause_time)
        await page.wait_for_load_state()
        # 重新获取页面高度
        scroll_height = await page.evaluate("document.body.scrollHeight")
        # 获取当前视口位置
        current_viewport_position = await page.evaluate("window.scrollY + window.innerHeight")
        # log.info(f"页面高度: {scroll_height}")
        # log.info(f"当前视口位置: {current_viewport_position}")
        log.debug(f"当前url:{page.url}")
        if current_viewport_position >= scroll_height or current_scroll_position >= scroll_height:
            # log.info("滚动到底部")
            break
        if max_attempt and i >= max_attempt:
            log.info(f"最大尝试次数: {i}, 停止")
            break
        if source == "next" and int(httpx.URL(page.url).params.get("p")) % page_size == 0:
            print("下一页")
            break
        # previous_height = new_height
