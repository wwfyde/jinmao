from typing import TypeVar, Type

from sqlalchemy import select, insert
from sqlalchemy.orm import DeclarativeBase, Session

from crawler import log
from crawler.db import engine
from crawler.models import ProductReview, ProductSKU, Product

T = TypeVar("T", bound=DeclarativeBase)


def field_filter(model: Type[T], data: dict | list[dict]) -> list[dict]:
    """
    过滤字段
    """
    if isinstance(data, dict):
        data = [data]
    new_data = []
    for item in data:
        new_data.append({key: value for key, value in item.items() if key in model.__table__.columns})
    return new_data

    # return {key: value for key, value in data.items() if key in model.__table__.columns}


def save_review_data(data: dict | list[dict]):
    """
    保存数据为json 和数据库
    主语
    """
    if isinstance(data, dict):
        data = [data]

    data: list = field_filter(ProductReview, data)

    with Session(engine) as session:
        inserted_ids = []
        for item in data:
            review_id = item.get("review_id")
            source = item.get("source")
            ...
            if review_id is None:
                log.error("review_id is None")
                continue

            review = (
                session.execute(
                    select(ProductReview).filter(ProductReview.review_id == review_id, ProductReview.source == source)
                )
                .scalars()
                .one_or_none()
            )
            if review:
                for key, value in item.items():
                    setattr(review, key, value)
                session.add(review)
                session.commit()
                session.refresh(review)
                log.debug(
                    f"更新评论[review]数据成功, id={review.id},review_id={review.review_id} , product_id={review.product_id}, source={review.source}"
                )

                inserted_ids.append(review.id)
            else:
                stmt = insert(ProductReview).values(item)
                review = session.execute(stmt)
                log.warning(review)
                insert_id = review.inserted_primary_key[0] if review.inserted_primary_key else None
                log.warning(insert_id)
                session.commit()
                if insert_id:
                    inserted_ids.append(insert_id)
                    review = (
                        session.execute(select(ProductReview).filter(ProductReview.id == insert_id))
                        .scalars()
                        .one_or_none()
                    )

                    log.debug(
                        f"插入评论[review]数据成功, id={review.id}, product_id={review.product_id}, source={review.source}"
                    )

        return inserted_ids if inserted_ids else None


def save_sku_data(data: dict | list[dict]) -> list | None:
    """
    保存数据为json 和数据库
    """
    if isinstance(data, dict):
        data = [data]
    data: list = field_filter(ProductSKU, data)
    inserted_ids = []
    with Session(engine) as session:
        for item in data:
            sku_id = item.get("sku_id")
            source = item.get("source")

            sku = (
                session.execute(select(ProductSKU).filter(ProductSKU.sku_id == sku_id, ProductSKU.source == source))
                .scalars()
                .one_or_none()
            )
            if sku:
                for key, value in item.items():
                    setattr(sku, key, value)
                session.add(sku)
                session.commit()
                session.refresh(sku)
                log.debug(
                    f"更新子款[SKU] 数据成功, id={sku.id}, sku_id={sku.sku_id}, product_id={sku.product_id}, source={sku.source}"
                )
                inserted_ids.append(sku.id)
            else:
                stmt = insert(ProductSKU).values(item)
                result = session.execute(stmt)
                session.commit()
                insert_id = result.inserted_primary_key[0] if result.inserted_primary_key else None
                if insert_id:
                    inserted_ids.append(insert_id)
                    sku = session.execute(select(ProductSKU).filter(ProductSKU.id == insert_id)).scalars().one_or_none()
                    log.debug(
                        f"插入子款[SKU] 数据成功, id={sku.id}, sku_id={sku.sku_id}, product_id={sku.product_id}, source={sku.source}"
                    )

        return inserted_ids if inserted_ids else None


def save_product_data(data: dict | list[dict]):
    """
    保存数据为json 和数据库
    """
    if isinstance(data, dict):
        data = [data]
    data: list = field_filter(Product, data)
    inserted_ids = []
    with Session(engine) as session:
        for item in data:
            product_id = item.get("product_id")
            source = item.get("source")
            product = (
                session.execute(select(Product).filter(Product.product_id == product_id, Product.source == source))
                .scalars()
                .one_or_none()
            )
            if product:
                for key, value in item.items():
                    setattr(product, key, value)
                session.add(product)
                session.commit()
                session.refresh(product)
                inserted_ids.append(product.id)
                log.debug(
                    f"更新商品[product]数据成功, id={product.id}, product_id={product.product_id}, source={product.source}"
                )
            else:
                log.info(f"insert product data: {item}")
                stmt = insert(Product).values(item)
                result = session.execute(stmt)
                session.commit()
                insert_id = result.inserted_primary_key[0] if result.inserted_primary_key else None
                if insert_id:
                    inserted_ids.append(insert_id)
                    product = session.execute(select(Product).filter(Product.id == insert_id)).scalars().one_or_none()
                    log.debug(
                        f"插入商品[product]数据成功, id={product.id}, product_id={product.product_id}, source={product.source}"
                    )
        return inserted_ids if inserted_ids else None


if __name__ == "__main__":
    log.debug("test")
    log.error("error")
    log.info("info")
    log.warning("warning")
    # print(save_product_data({"product_id": 12, "name": "test", "source": "gap2"}))
    # print(save_review_data({"review_id": 3, "product_name": "test2", "source": "gap", "product_id": 1}))
    print(
        "已插入数据: ",
        save_product_data(
            {"product_id": 999999, "sku_id": 5, "product_name": "test3", "source": "gap", "attributes": {"test": 12}}
        ),
    )
