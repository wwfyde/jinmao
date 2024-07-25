from sqlalchemy import select
from sqlalchemy.orm import Session

from crawler.db import engine
from crawler.models import Product

__doc__ = """批量处理tags"""

with Session(engine) as session:
    stmt = select(Product).where(Product.tags.is_not(None))
    results = session.execute(stmt).scalars().all()
    for result in results:
        print(result.tags, result.product_id)
        if '金茂' in result.tags:
            # result.tags = [tag for tag in result.tags if tag != '金茂']
            result.tags = ['Singtex' if tag == '金茂' else tag for tag in result.tags]

            print(result.tags)
            session.add(result)
    session.commit()
