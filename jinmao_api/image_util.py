from sqlalchemy import select
from sqlalchemy.orm import Session

from crawler.db import engine
from crawler.models import ProductSKU

__doc__ = """批量处理tags"""

with Session(engine) as session:
    stmt = select(ProductSKU).where(ProductSKU.source == 'jcpenney')
    results: list[ProductSKU] = session.execute(
        select(ProductSKU).where(ProductSKU.source == 'jcpenney')).scalars().all()
    for result in results:
        print(result.model_image_urls, result.product_id)
        images = result.model_image_urls
        if isinstance(images, list) and images:
            result.image_url = images[0]
            result.outer_image_url = images[0]
            session.add(result)
            print(result.image_url)
            print(result.outer_image_url)
    session.commit()
