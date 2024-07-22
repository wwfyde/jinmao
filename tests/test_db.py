from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from crawler.db import engine
from crawler.deps import get_logger
from crawler.models import ProductReview, Product

log = get_logger("test")


def test_insert_or_update():
    with Session(engine) as session:
        item = {
            "product_id": 999993444,
            "sku_id": 1,
            "rating": 5,
            "title": "测试",
            "source": "other"
        }
        id = item["product_id"]
        # result = session.execute(text("select version()")).scalars().one_or_none()
        review = session.execute(select(ProductReview).filter(ProductReview.product_id == id)).scalars().one_or_none()
        if review:
            log.info("已存在")
            log.info(review)
            for key, value in item.items():
                setattr(review, key, value)

                log.info(key, value)
            log.info(review.id, review.product_id)
            session.add(review)
            session.commit()
            session.refresh(review)
            log.info(review)
        else:
            log.info("不存在")

            stmt = insert(ProductReview).values(item)
            result = session.execute(stmt)
            session.commit()
            log.info(result)


def test_product_sku():
    with Session(engine) as session:
        result: Product = session.execute(
            select(Product).where(Product.source == 'gap', Product.product_id == '728681')).scalars().one_or_none()
        if result:
            assert result.product_id == '728681'
