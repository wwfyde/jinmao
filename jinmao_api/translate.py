import asyncio
import json
import os
from concurrent.futures import ProcessPoolExecutor
from typing import Literal

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from crawler.config import settings
from crawler.db import async_engine_test
from crawler.models import ProductReview
from jinmao_api import log

__doc__ = """
从uat数据库拿到数据, 并将其翻译
"""

from jinmao_api.schemas import ProductReviewTranslationSchema


async def ai_translator(data: dict, llm_channel: Literal['glm4_air', 'ark_doubao', 'claude_haiku'] = 'glm4_air') -> str:
    client = AsyncOpenAI(
        api_key=getattr(settings, llm_channel).api_key,
        base_url=getattr(settings, llm_channel).base_url,
    )

    chat_completion = await client.chat.completions.create(
        model=getattr(settings, llm_channel).model,
        messages=[
            {"role": "system", "content": settings.translate_prompt},
            {"role": "user", "content": str(data)},
        ],
    )
    result = chat_completion.choices[0].message.content
    log.info(result)
    log.info(chat_completion.usage)
    return result


async def main():
    # get the data from the database
    stmt = select(ProductReview)
    async_session = async_sessionmaker(async_engine_test)
    async with async_session() as session:
        result = await session.execute(stmt)
        product_reviews_in_uat = result.scalars().first()
        log.info(f"一共获取到 {product_reviews_in_uat} 条数据")
        review_obj = ProductReviewTranslationSchema.model_validate(product_reviews_in_uat)
        review_dict = review_obj.model_dump()
        print(review_dict)
        result = await ai_translator(review_dict)

        try:
            # 将字符串转换为json对象
            tranlated_result = json.loads(result)
            review_obj = ProductReviewTranslationSchema.model_validate(tranlated_result)
        except Exception as e:
            log.error(f"翻译后的数据验证失败, {result}")
            log.error(e)
            review_obj = {}
        # 将翻译后的数据写入数据
        if review_obj:
            session.add(review_obj)
            await session.commit()
            print(result)
        else:
            log.error(f"翻译失败, {result}")

    log.info("任务执行完毕")
    await async_engine_test.dispose()

    chunks = []
    loop = asyncio.get_running_loop()
    max_workers = 800 or os.cpu_count()
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        tasks = [loop.run_in_executor(executor, ai_translator, data) for data in chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                log.error(result)
            else:
                log.info(result)


if __name__ == '__main__':
    # asyncio.run(ai_translator({"hello": "world"}))
    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)
    # loop.run_until_complete(main())
    # loop.close()
    asyncio.run(main())
