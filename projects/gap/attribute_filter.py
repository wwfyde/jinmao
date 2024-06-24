__doc__ = """
你是一名电商领域的数据清洗和分析专家, 请根据我输入的对象(一个python列表或JavaScript数组), 依据每一列的信息为其设置键名, 并将原值作为键的值,  你也根据你的领域知识为某个字段设置键名:
可能的键名有:
    - 材质: material
    - 产地: origin
    - 领口: neckline
    - 适合场景: fit
    - 面料: fabric
    - 服装风格: style 
    - 尺寸: size
# 约束
- 最终数据为一个 json给我 
- 键的命名风格下划线格式(snake_case, pothole_case), 比如: product_id
- 必须字段:  fit, origin, fabric, material, neckline, size, style; 如果这些必选字段未提起到, 请赋值字符串 "-"
- 对于额外字段, 请根据输入对象的上下文信息推断其键名, 可以结合各大电商平台的数据库和商品属性的常见字段来为其设置键名
- #880272"类似的数据,是商品ID, 可将其键设置为 "priduct_id"
- 提取输入所有字段, 为字段设置合适的键名
- fit&size相关字段的示例:  [ "Mid rise.", "Fuller through the thigh.", "Tapered leg opening.", "Model is 6'2"/188 cm with a 31"/79 cm waist, wearing a regular Gap size 32x32."]
- product_details相关字段的示例: ["Soft, stretch chambray cotton resort shirt.","Resort collar.","Short sleeves.","Button front.", "Patch pocket at chest.","Allover floral print.","#440866"]
- fabric&care 相关字段示例: ["98% cotton, 2% elastane","Machine wash.","Imported."]

# 异常处理
- 不要有任何你是一个AI, 或LLM或机器人的提醒


# 输入示例: 
["* Fit: Slim. A fit & flare silhouette that sits close to the body & flares at the waist.", 
"Hits below the knee.", 
"Models wearing Gap size S are 5'8\"–5'11\" (172–180 cm) with 23.5–26\" (60–66 cm) waist & 33–38\" (84–97 cm) hips.", 
"Models wearing Gap size XL are 5'8\"–5'11\" (172–180 cm) with 34–36” (86–91 cm) waist & 45–50\" (114–127 cm) hips.", 
"Soft cotton midi dress.", "Square neck.", 
"Spaghetti straps.", "Front slant pockets.", 
"Handkerchief hem.", 
"#880272", 
"Cotton 100%", "Machine wash.", 
"Imported."
]

# 输出示例
{
    "fit": "Slim. A fit & flare silhouette that sits close to the body & flares at the waist.",
    "origin": "Imported.",
    "fabric": "Cotton 100%",
    "size": "Models wearing Gap size S are 5'8\"–5'11\" (172–180 cm) with 23.5–26\" (60–66 cm) waist & 33–38\" (84–97 cm) hips.",
    ...
}

"""

import asyncio
import json

import httpx
import redis.asyncio as redis
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from crawler import log
from crawler.config import settings
from crawler.db import engine
from crawler.models import Product


async def attributes_filter(data: str):
    proxies = {"http://": settings.proxy_url, "https://": settings.proxy_url}
    http_client = httpx.AsyncClient(proxies=proxies)
    client = AsyncOpenAI(http_client=http_client)
    chat_completion = await client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": __doc__,
            },
            {
                "role": "user",
                "content": data,
            },
        ],
        model="gpt-4o",
    )
    print(chat_completion.choices[0].message.content)
    return chat_completion.choices[0].message.content.replace("```json", "").replace("```", "").strip()


async def process_product(product_db, semaphore, session):
    async with semaphore:
        log.debug(f"{product_db.product_id=}")
        attributes_raw = product_db.attributes_raw
        gender = product_db.gender
        product_id = product_db.product_id
        r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
        async with r:
            product_attribute_status = await r.get(f"product_attribute_status:gap:{gender}:default:{product_id}")
            if product_attribute_status == "done":
                log.warning(f"product_id: {product_id} attributes is done")
                return
        if not attributes_raw:
            log.warning(f"product_id: {product_id} attributes_raw is None")
            return
        try:
            start_time = asyncio.get_event_loop().time()
            attributes = await attributes_filter(str(attributes_raw))
            end_time = asyncio.get_event_loop().time()
            log.debug(f"{product_id=}数据清洗耗时: {(end_time - start_time):.3f}")
            log.warning(f"提取到: product_id: {product_id} attributes: {attributes}")
            product_db.attributes = json.loads(attributes)
            session.add(product_db)
            session.commit()
            session.refresh(product_db)
            log.info(f"product_id: {product_db.product_id} attributes: {product_db.attributes}")
            r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
            async with r:
                product_attribute_status = await r.set(
                    f"product_attribute_status:gap:{gender}:default:{product_id}", "done"
                )
                log.info(f"product_attribute_status: {product_attribute_status}")
            await asyncio.sleep(1)
        except Exception as exc:
            log.error(f"product_id: {product_id} error: {exc}")
            return


async def main():
    with Session(engine) as session:
        stmt = select(Product).where(Product.source == "gap")  # noqa
        results: list[Product] = session.execute(stmt).scalars().all()
        semaphore = asyncio.Semaphore(40)
        for product_db in results:
            await process_product(product_db, semaphore=semaphore, session=session)


if __name__ == "__main__":
    asyncio.run(main())
