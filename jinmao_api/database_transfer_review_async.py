import asyncio
from typing import Sequence, List
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select
from crawler import models, models_bak  # noqa
from crawler.db import async_engine, async_engine_test
from jinmao_api import log


async def fetch_data(session: AsyncSession, source: str) -> Sequence[models_bak.ProductReview]:
    stmt = select(models_bak.ProductReview).where(models_bak.ProductReview.source == source)
    result = await session.execute(stmt)
    return result.scalars().all()


async def insert_data(session: AsyncSession, product_reviews: Sequence[models_bak.ProductReview]):
    tasks = []
    log.info("批量插入数据中")
    for product_review in product_reviews:
        tasks.append(insert_single_review(session, product_review))
    await asyncio.gather(*tasks)


async def insert_single_review(session: AsyncSession, product_review: models_bak.ProductReview):
    stmt = select(models.ProductReview).where(
        models.ProductReview.product_id == product_review.product_id,
        models.ProductReview.review_id == product_review.review_id
    )
    result = await session.execute(stmt)
    product_review_in_test = result.scalars().one_or_none()

    if product_review_in_test:
        log.info(f"product_review {product_review.id} already exists")
        return

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
    await session.commit()


async def main(source_list: List[str]):
    # 创建异步会话

    async_session_uat = async_sessionmaker(async_engine)
    async_session_test = async_sessionmaker(async_engine_test)

    async with async_session_uat() as session_uat:
        tasks = []
        for source in source_list:
            tasks.append(fetch_data(session_uat, source))
        results = await asyncio.gather(*tasks)

        all_product_reviews = [review for sublist in results for review in sublist]
        log.info(f"共有{len(all_product_reviews)}条数据")

    chunk_size = 500  # 每次插入100条记录
    chunks = [all_product_reviews[i:i + chunk_size] for i in range(0, len(all_product_reviews), chunk_size)]

    async with async_session_test() as session_test:
        insert_tasks = []
        for chunk in chunks:
            insert_tasks.append(insert_data(session_test, chunk))
        await asyncio.gather(*insert_tasks)
        # await session_test.commit()


if __name__ == '__main__':
    source_list = ['target', 'gap', 'next', 'jcpenney']
    asyncio.run(main(source_list))
