from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from crawler.db import engine
from crawler.models import ProductReview


def test_insert_or_update():
    with Session(engine) as session:
        item = {
            "product_id": 33,
            "sku_id": 1,
            "rating": 5,
            "title": "测试",
            "review": "good",
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
