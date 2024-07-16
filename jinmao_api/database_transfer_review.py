from concurrent.futures import ProcessPoolExecutor
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from crawler import models, models_bak  # noqa

__doc__ = """
将数据迁移到新的数据库
"""

from crawler.db import engine, engine_test
from jinmao_api import log


def main(source: str = "jcpenney"):
    session_uat = sessionmaker(engine)
    # 从UAT数据库读取数据
    with session_uat() as a_session:
        stmt = select(models_bak.ProductReview)
        result = a_session.execute(stmt)
        product_reviews_in_uat: Sequence[models_bak.ProductReview] = result.scalars().all()
        # data = [product for product in products]

        # for product in products:
        #     async_session
        #     # session.execute("SET FOREIGN

        log.info(f"一共获取到 {len(product_reviews_in_uat)} 条数据")

    # 对数据进行分开
    chunk_size = 500

    chunks = [product_reviews_in_uat[i:i + chunk_size] for i in range(0, len(product_reviews_in_uat), chunk_size)]
    # 将数据写入测试数据库
    max_workers = 40
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        executor.map(worker, chunks)


def worker(chunk):
    session_test = sessionmaker(engine_test)
    with session_test() as session:
        for product_review in chunk:
            stmt = select(models.ProductReview).where(models.ProductReview.product_id == product_review.product_id,
                                                      models.ProductReview.review_id == product_review.review_id)
            result = session.execute(stmt)
            product_review_in_test = result.scalars().one_or_none()

            # 当数据已存在时, 跳过
            if product_review_in_test:
                log.info(f"product_review {product_review.id} already exists")
                continue
            # log.debug(f"add , product_review: {product_review.id=}, {product_review.review_id=}, p ")
            session.add(models.ProductReview(
                id=product_review.id,
                review_id=product_review.review_id,
                source=product_review.source,
                product_id=product_review.product_id,
                sku_id=product_review.sku_id,
                rating=product_review.rating,
                title=product_review.title,
                comment=product_review.comment,
                photos=product_review.photos,
                outer_photos=product_review.outer_photos,
                nickname=product_review.nickname,
                helpful_votes=product_review.helpful_votes,
                not_helpful_votes=product_review.not_helpful_votes,
                is_deleted=product_review.is_deleted,
                gathered_at=product_review.created_at,
                last_gathered_at=product_review.updated_at,
                created_at=product_review.inner_created_at,
                updated_at=product_review.inner_updated_at,

            ))
        session.commit()
        log.info("chunk commit")


if __name__ == '__main__':
    main()
