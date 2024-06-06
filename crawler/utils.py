import json
import uuid
from pathlib import Path

import oss2
from fastapi import HTTPException
from playwright.async_api import Page

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
