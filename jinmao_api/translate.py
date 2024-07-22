import asyncio
import json
import time
from typing import Literal

from openai import AsyncOpenAI
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import sessionmaker

from crawler.config import settings
from crawler.db import async_engine, engine
from crawler.models import ProductReview, ProductReviewTranslation, Product, ProductTranslation
from jinmao_api import log

__doc__ = """
从uat数据库拿到数据, 并将其翻译
"""

from jinmao_api.schemas import ProductReviewTranslationSchema, ProductTranslationSchema


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


async def review_run():
    # get the data from the database
    async_session = async_sessionmaker(async_engine)
    async with async_session() as session:
        stmt = select(ProductReview).where(ProductReview.source == 'gap', ProductReview.product_id == '728681')
        result = await session.execute(stmt)
        product_reviews_in_uat = result.scalars().all()

        log.info(f"一共获取到 {len(product_reviews_in_uat)} 条数据")
        for product_review_in_uat in product_reviews_in_uat:
            log.debug(f"正在处理数据: {product_review_in_uat},")
            # review_obj = ProductReviewTranslationSchema.model_validate(product_review_in_uat)
            # print(review_obj)
            # review_dict = review_obj.model_dump()
            review_dict = dict(title=product_review_in_uat.title, comment=product_review_in_uat.comment)
            # print(review_dict)
            result = await ai_translator(review_dict, llm_channel='ark_doubao')
            log.info(f"翻译后的结果: {result}")

            try:
                # 将字符串转换为json对象
                tranlated_result = json.loads(result)
                review_obj = ProductReviewTranslationSchema.model_validate(tranlated_result).model_dump(
                    exclude_unset=True)
            except Exception as e:
                log.error(f"翻译后的数据验证失败, {result}")
                log.error(e)
                continue
                # review_obj = ProductReviewTranslationSchema.model_validate({}).model_dump(exclude_unset=True)
            # 将翻译后的数据更新或插入
            product_review_translation: ProductReviewTranslation = (await session.execute(
                select(ProductReviewTranslation).where(
                    ProductReviewTranslation.review_id == product_review_in_uat.review_id,
                    ProductReviewTranslation.source == product_review_in_uat.source)
            )).scalars().one_or_none()
            if product_review_translation:
                for key, value in review_obj.items():
                    setattr(product_review_translation, key, value)
                product_review_translation.review_id = product_review_in_uat.review_id
                product_review_translation.source = product_review_in_uat.source
                product_review_translation.language_code = "zh"
                product_review_translation.product_id = product_review_in_uat.product_id

                session.add(product_review_translation)
                await session.commit()
                print(result)
                log.info(f"更新数据: {review_obj}")
            else:

                translated_result_db = ProductReviewTranslation()
                if review_obj:
                    for key, value in review_obj.items():
                        setattr(translated_result_db, key, value)
                    translated_result_db.review_id = product_review_in_uat.review_id
                    translated_result_db.source = product_review_in_uat.source
                    translated_result_db.language_code = "zh"
                    translated_result_db.product_id = product_review_in_uat.product_id
                    session.add(translated_result_db)
                    await session.commit()
                    log.info(f"插入数据: {review_obj}")
                    print(result)
                else:
                    log.error(f"翻译失败, {result}")

    log.info("任务执行完毕")
    await async_engine.dispose()
    # 
    # chunks = []
    # loop = asyncio.get_running_loop()
    # max_workers = 800 or os.cpu_count()
    # with ProcessPoolExecutor(max_workers=max_workers) as executor:
    #     tasks = [loop.run_in_executor(executor, ai_translator, data) for data in chunks]
    #     results = await asyncio.gather(*tasks, return_exceptions=True)
    #     for result in results:
    #         if isinstance(result, Exception):
    #             log.error(result)
    #         else:
    #             log.info(result)


async def review_run_sync():
    # get the data from the database
    session = sessionmaker(engine)
    with session() as session:
        stmt = select(ProductReview).where(ProductReview.source == 'gap', ProductReview.product_id == '728681')
        result = session.execute(stmt)
        product_reviews_in_uat = result.scalars().all()

        log.info(f"一共获取到 {len(product_reviews_in_uat)} 条数据")
        for product_review_in_uat in product_reviews_in_uat:
            log.debug(f"正在处理数据: {product_review_in_uat}")
            # review_obj = ProductReviewTranslationSchema.model_validate(product_review_in_uat)
            # print(review_obj)
            # review_dict = review_obj.model_dump()
            review_dict = dict(title=product_review_in_uat.title, comment=product_review_in_uat.comment)
            # print(review_dict)
            result = await ai_translator(review_dict, llm_channel='ark_doubao')
            log.info(f"翻译后的结果: {result}")

            try:
                # 将字符串转换为json对象
                tranlated_result = json.loads(result)
                review_obj = ProductReviewTranslationSchema.model_validate(tranlated_result).model_dump(
                    exclude_unset=True)
            except Exception as e:
                log.error(f"翻译后的数据验证失败, {result}")
                log.error(e)
                continue
                # review_obj = ProductReviewTranslationSchema.model_validate({}).model_dump(exclude_unset=True)
            # 将翻译后的数据更新或插入
            product_review_translation: ProductReviewTranslation = session.execute(
                select(ProductReviewTranslation).where(
                    ProductReviewTranslation.review_id == product_review_in_uat.review_id,
                    ProductReviewTranslation.source == product_review_in_uat.source)
            ).scalars().one_or_none()
            if product_review_translation:
                for key, value in review_obj.items():
                    setattr(product_review_translation, key, value)
                product_review_translation.review_id = product_review_in_uat.review_id
                product_review_translation.source = product_review_in_uat.source
                product_review_translation.language_code = "zh"
                product_review_translation.product_id = product_review_in_uat.product_id

                session.add(product_review_translation)
                session.commit()
                print(result)
                log.info(f"更新数据: {review_obj}")
            else:

                translated_result_db = ProductReviewTranslation()
                if review_obj:
                    for key, value in review_obj.items():
                        setattr(translated_result_db, key, value)
                    translated_result_db.review_id = product_review_in_uat.review_id
                    translated_result_db.source = product_review_in_uat.source
                    translated_result_db.language_code = "zh"
                    translated_result_db.product_id = product_review_in_uat.product_id
                    session.add(translated_result_db)
                    session.commit()
                    log.info(f"插入数据: {review_obj}")
                    print(result)
                else:
                    log.error(f"翻译失败, {result}")

    log.info("任务执行完毕")
    # 
    # chunks = []
    # loop = asyncio.get_running_loop()
    # max_workers = 800 or os.cpu_count()
    # with ProcessPoolExecutor(max_workers=max_workers) as executor:
    #     tasks = [loop.run_in_executor(executor, ai_translator, data) for data in chunks]
    #     results = await asyncio.gather(*tasks, return_exceptions=True)
    #     for result in results:
    #         if isinstance(result, Exception):
    #             log.error(result)
    #         else:
    #             log.info(result)


async def product_run():
    # get the data from the database
    async_session = async_sessionmaker(async_engine)
    async with async_session() as session:
        stmt = select(Product).where(Product.source == 'gap')
        result = await session.execute(stmt)
        products_in_uat = result.scalars().all()
        log.info(f"一共获取到 {len(products_in_uat)} 条数据")
        for product_in_uat in products_in_uat:
            product_obj = ProductTranslationSchema.model_validate(product_in_uat)
            product_dict = product_obj.model_dump()
            print(product_dict)
            result = await ai_translator(product_dict, llm_channel='ark_doubao')

            try:
                # 将字符串转换为json对象
                tranlated_result = json.loads(result)
                product_obj = ProductTranslationSchema.model_validate(tranlated_result).model_dump(exclude_unset=True)
            except Exception as e:
                log.error(f"翻译后的数据验证失败, {result}")
                log.error(e)
                # product_obj = ProductTranslationSchema.model_validate({}).model_dump(exclude_unset=True)
                continue
            # 将翻译后的数据更新或插入数据
            product_translation: ProductTranslation = (await session.execute(
                select(ProductTranslation).where(ProductTranslation.product_id == product_obj['product_id'],
                                                 ProductTranslation.source == product_obj['source'])
            )).scalars().one_or_none()
            if product_translation:
                for key, value in product_obj.items():
                    setattr(product_translation, key, value)
                session.add(product_translation)
                await session.commit()
                print(result)
                log.info(f"更新数据: {product_obj}")
            else:

                translated_result_db = ProductTranslation()
                if product_obj:
                    for key, value in product_obj.items():
                        setattr(translated_result_db, key, value)
                    session.add(translated_result_db)
                    await session.commit()
                    print(result)
                    log.info(f"插入数据: {product_obj}")
                else:
                    log.error(f"翻译失败, {result}")

    log.info("任务执行完毕")
    await async_engine.dispose()
    # 
    # chunks = []
    # loop = asyncio.get_running_loop()
    # max_workers = 800 or os.cpu_count()
    # with ProcessPoolExecutor(max_workers=max_workers) as executor:
    #     tasks = [loop.run_in_executor(executor, ai_translator, data) for data in chunks]
    #     results = await asyncio.gather(*tasks, return_exceptions=True)
    #     for result in results:
    #         if isinstance(result, Exception):
    #             log.error(result)
    #         else:
    #             log.info(result)


async def product_run_sync():
    # get the data from the database
    session = sessionmaker(engine)
    with session() as session:
        stmt = select(Product).where(Product.source == 'gap')
        result = session.execute(stmt)
        products_in_uat: list[Product] = result.scalars().all()
        log.info(f"一共获取到 {len(products_in_uat)} 条数据")
        # 获取所有需要检查的 product_id 和 source 组合
        product_ids_sources = [(product.product_id, product.source) for product in products_in_uat]

        existing_translations_stmt = select(ProductTranslation.product_id, ProductTranslation.source).where(
            tuple_(ProductTranslation.product_id, ProductTranslation.source).in_(product_ids_sources)
        )
        existing_translations_result = session.execute(existing_translations_stmt)
        existing_translations = set(existing_translations_result.fetchall())
        for product_in_uat in products_in_uat:
            start_time = time.time()
            if (product_in_uat.product_id, product_in_uat.source) in existing_translations:
                log.info(f"产品 {product_in_uat.product_id} 已存在翻译，跳过")
                continue
            try:
                product_obj = ProductTranslationSchema.model_validate(product_in_uat)
            except Exception as exc:
                log.error(f"数据验证失败, {product_in_uat.product_id}, error: {exc}")
                continue
            product_dict = product_obj.model_dump()
            print(product_dict)

            result = await ai_translator(product_dict, llm_channel='ark_doubao')

            try:
                # 将字符串转换为json对象
                tranlated_result = json.loads(result)
                product_obj = ProductTranslationSchema.model_validate(tranlated_result).model_dump(exclude_unset=True)
            except Exception as e:
                log.error(f"翻译后的数据验证失败, {result}")
                log.error(e)
                # product_obj = ProductTranslationSchema.model_validate({}).model_dump(exclude_unset=True)
                continue
            # 将翻译后的数据更新或插入数据
            product_translation: ProductTranslation = session.execute(
                select(ProductTranslation).where(ProductTranslation.product_id == product_in_uat.product_id,
                                                 ProductTranslation.source == product_in_uat.source)
            ).scalars().one_or_none()
            if product_translation:
                for key, value in product_obj.items():
                    setattr(product_translation, key, value)
                product_translation.product_id = product_in_uat.product_id
                product_translation.source = product_in_uat.source
                session.add(product_translation)
                session.commit()
                print(result)
                log.info(f"更新数据: {product_obj}")
            else:

                translated_result_db = ProductTranslation()
                if product_obj:
                    for key, value in product_obj.items():
                        setattr(translated_result_db, key, value)
                    translated_result_db.product_id = product_in_uat.product_id
                    translated_result_db.source = product_in_uat.source
                    session.add(translated_result_db)
                    session.commit()
                    print(result)
                    log.info(f"插入数据: {product_obj}")
                else:
                    log.error(f"翻译失败, {result}")
            end_time = time.time()
            log.info(f"单条任务执行完毕, 耗时: {end_time - start_time} 秒")

    log.info("任务执行完毕")
    # await async_engine.dispose()
    

if __name__ == '__main__':
    # asyncio.run(ai_translator({"hello": "world"}))
    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)
    # loop.run_until_complete(main())
    # loop.close()
    asyncio.run(product_run_sync())
    # asyncio.run(review_run_sync())
    # asyncio.run(review_run())
