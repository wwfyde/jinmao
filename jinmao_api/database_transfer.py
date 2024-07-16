import asyncio
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from crawler import models, models_bak  # noqa

__doc__ = """
将数据迁移到新的数据库
"""

from crawler.db import engine, engine_test


async def main(source: str = "jcpenney"):
    session_uat = sessionmaker(engine)
    # 从UAT数据库读取数据
    with session_uat() as a_session:
        stmt = select(models_bak.Product).where(models_bak.Product.source == source)
        result = a_session.execute(stmt)
        products_in_uat: Sequence[models_bak.Product] = result.scalars().all()
        # data = [product for product in products]

        # for product in products:
        #     async_session
        #     # session.execute("SET FOREIGN

    # 将数据写入测试数据库
    session_test = sessionmaker(engine_test)
    with session_test() as session:
        for product in products_in_uat:
            stmt = select(models.Product).where(models.Product.product_id == product.product_id,
                                                models.Product.source == source)
            result = session.execute(stmt)
            product_in_test = result.scalars().one_or_none()

            # 当数据已存在时, 跳过
            if product_in_test:
                continue
            session.add(models.Product(
                id=product.id,
                product_id=product.product_id,
                source=product.source,
                product_name=product.product_name,
                primary_sku_id=product.sku_id,
                brand=product.brand,
                product_url=product.product_url,
                rating=product.rating,
                review_count=product.review_count,
                rating_count=product.rating_count,
                attributes=product.attributes,
                description=product.description,
                attributes_raw=product.attributes_raw,
                category=product.category,
                # category=product.category.split(" ")[-1].title() if product.category else None,
                gender=product.gender,
                released_at=product.released_at,
                tags=product.tags,
                is_review_analyzed=product.is_review_analyzed,
                review_analyses=product.review_analyses,
                extra_review_analyses=product.extra_review_analyses,
                extra_metrics=product.extra_metrics,
                review_statistics=product.review_statistics,
                extra_review_statistics=product.extra_review_statistics,
                review_summary=product.review_summary,
                remark=product.remark,
                category_id=product.category_id,
                is_deleted=product.is_deleted,
                gathered_at=product.created_at,
                last_gathered_at=product.updated_at,
                created_at=product.inner_created_at,
                updated_at=product.inner_updated_at,

            ))
        session.commit()


if __name__ == '__main__':
    asyncio.run(main())
