import asyncio
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from crawler import models, models_bak  # noqa

__doc__ = """
将数据迁移到新的数据库
"""

from crawler.db import engine, engine_test


# 将target的sku存入test数据库
async def main(source: str = "gap"):
    session_uat = sessionmaker(engine)
    # 从UAT数据库读取数据
    with session_uat() as a_session:
        stmt = select(models_bak.Product).where(models_bak.Product.source == source)
        result = a_session.execute(stmt)
        product_skus_in_uat: Sequence[models_bak.Product] = result.scalars().all()
        # data = [product for product in products]

        # for product in products:
        #     async_session
        #     # session.execute("SET FOREIGN

    # 将数据写入测试数据库
    session_test = sessionmaker(engine_test)
    with session_test() as session:
        for product_sku in product_skus_in_uat:
            stmt = select(models.ProductSKU).where(models.ProductSKU.product_id == product_sku.product_id,
                                                   models.ProductSKU.sku_id == product_sku.sku_id,

                                                   models.ProductSKU.source == source)
            result = session.execute(stmt)
            product_in_test = result.scalars().one_or_none()

            # 当数据已存在时, 跳过
            if product_in_test:
                continue
            session.add(models.ProductSKU(
                sku_id=product_sku.sku_id,
                source=product_sku.source,
                product_id=product_sku.product_id,
                size=product_sku.size,
                color=product_sku.color,
                material=product_sku.material,
                # sku_name=None,  # 需要从product_sku表中读取
                product_url=product_sku.product_url,
                image_url=product_sku.image_url,
                outer_image_url=product_sku.outer_image_url,
                model_image_urls=product_sku.model_image_urls,
                outer_model_image_urls=product_sku.outer_model_image_urls,
                # inventory=None,
                # inventory_status=None,
                is_deleted=product_sku.is_deleted,
                gathered_at=product_sku.created_at,
                last_gathered_at=product_sku.updated_at,
                created_at=product_sku.inner_created_at,
                updated_at=product_sku.inner_updated_at,

            ))
        session.commit()


if __name__ == '__main__':
    asyncio.run(main())
