from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from api import log
from crawler.config import settings
from crawler.db import engine
from crawler.models import Product
from crawler.store import save_sku_data, save_product_data
from crawler.utils import upload_image


def process_directory(data_dir: Path | str, source: str = "gap"):
    """
    处理目录，获取每个 product_id 的所有 sku_id 和图片，并上传到 OSS
    :param data_dir: 根目录路径
    :param source: 数据来源
    :return: 包含每个 product_id 的 sku_id 和图片 URL 的字典列表
    """
    result = []
    if isinstance(data_dir, str):
        data_dir = Path(data_dir)
    # 拼接数据目录路径
    source_dir = data_dir.joinpath(source)

    # 迭代商品目录
    # 获取商品目录
    for primary_category_dir in source_dir.iterdir():
        if primary_category_dir.is_dir():
            print(primary_category_dir)
            primary_category_name = primary_category_dir.name
            print(primary_category_name)
            for sub_category_dir in primary_category_dir.iterdir():
                if primary_category_dir.is_dir():
                    sub_category_name = sub_category_dir.name
                    print(sub_category_name)
                    for product_dir in sub_category_dir.iterdir():
                        print(product_dir)
                        if product_dir.is_dir():
                            # 获取目录ID
                            product_id = product_dir.name
                            product_data = {"product_id": product_id, "skus": []}
                            # 从数据库获取 product_id 对应的 sku_id
                            product_sku_id = None
                            with Session(engine) as session:
                                stmt = select(Product.sku_id).where(
                                    Product.product_id == product_id, Product.source == source
                                )

                                product_sku_id = session.execute(stmt).scalar_one_or_none()

                            for sku_dir in product_dir.iterdir():
                                if sku_dir.is_dir():
                                    sku_id = sku_dir.name
                                    sku_data = {"sku_id": sku_id, "images": []}
                                    sku_images = []
                                    for model_dir in sku_dir.iterdir():
                                        if model_dir.is_dir() and model_dir.name == "model":
                                            for image_file in sorted(
                                                model_dir.iterdir(), key=lambda x: int(x.name.split("-")[1])
                                            ):
                                                if image_file.is_file() and image_file.suffix in [
                                                    ".jpg",
                                                    ".jpeg",
                                                    ".png",
                                                ]:
                                                    image_type = "model" if "_1_" in image_file.name else "product"
                                                    oss_path = (
                                                        f"{product_id}/{sku_id}/{model_dir.name}/{image_file.name}"
                                                    )
                                                    with image_file.open("rb") as f:
                                                        content = f.read()
                                                        source = "gap"
                                                        image_url = upload_image(
                                                            str(image_file).split("/")[-1],
                                                            content,
                                                            prefix=f"crawler/{source}",
                                                            rename=False,
                                                        )
                                                        print(image_url)
                                                        sku_images.append(image_url)
                                                    sku_data["images"].append({"type": image_type, "url": image_url})
                                    sku_data_db = dict(
                                        product_id=product_id,
                                        sku_id=sku_id,
                                        source=source,
                                    )
                                    if len(sku_images) > 0:
                                        sku_data_db["image_url"] = sku_images[-1]
                                        sku_data_db["model_image_url"] = sku_images[0]
                                        sku_data_db["model_image_urls"] = sku_images
                                    print(sku_data_db)
                                    save_sku_data(sku_data_db)
                                    log.info(f"Saving sku data for {sku_id}")
                                    if product_sku_id and sku_id == product_sku_id:
                                        log.info(f"Saving product data for {product_id}")
                                        save_product_data(sku_data_db)

                                    product_data["skus"].append(sku_data)

                            result.append(product_data)

    return result


if __name__ == "__main__":
    data_dir = settings.data_dir
    log.info(f"Processing directory: {str(data_dir)}")
    result = process_directory(data_dir, source="gap")
    print(result)
