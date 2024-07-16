import asyncio
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from crawler import models, models_bak  # noqa

__doc__ = """
将数据迁移到新的数据库
"""

from crawler.db import engine, engine_test


async def main(source: str = "target"):
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
            stmt = select(models.ProductDetail).where(models.ProductDetail.product_id == product.product_id,
                                                      models.ProductDetail.source == source)
            result = session.execute(stmt)
            product_in_test = result.scalars().one_or_none()

            # 当数据已存在时, 跳过
            if product_in_test:
                continue
            session.add(models.ProductDetail(
                id=product.id,
                product_id=product.product_id,
                source=product.source,
                material=product.material,
                neckline=product.neckline,
                store=product.store,
                # fabric=product.fabric,
                origin=product.origin,
                length=product.length,
                fit=product.fit,
                # vendor=product.vendor,
                category_breadcrumbs=product.category_breadcrumbs if source != 'gap' else product.category,
                parent_category=product.parent_category,
                sub_category=product.sub_category,
                lot_id=product.lot_id,

            ))
        session.commit()


if __name__ == '__main__':
    asyncio.run(main())
