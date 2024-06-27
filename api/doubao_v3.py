import asyncio
import json
import logging
import random
import time
from typing import cast

from jinja2 import Template
from openai import AsyncOpenAI
from sqlalchemy import select, ColumnElement
from sqlalchemy.orm import Session

from api.schemas import ProductReviewAnalysis, ReviewAnalysisMetrics, ProductReviewSchema
from crawler import log
from crawler.config import settings
from crawler.db import engine
from crawler.models import ProductReview

crawler_logger = logging.getLogger("crawler")
crawler_logger.setLevel(logging.INFO)
log_libraries = ["httpx", "httpcore", "openai"]
for library in log_libraries:
    library_logger = logging.getLogger(library)
    library_logger.setLevel(logging.INFO)

settings.ark_prompt = """用途：作为电子商务和情感分析专家，全面分析客户反馈,根据评论的情感倾向和语义内容，推断并给出每个属性的评分
功能说明：该模块不仅分析评论中直接提到的内容，还推断并评分以下属性：quality, warmth, comfort, softness, preference, repurchase_intent, appearance, fit, {{ extra_metrics }}。每个属性的最高分为10分。
实现方法：通过综合分析评论的整体情感和语义内容，即使某些属性没有直接提到，也能进行推断和评分。
输入：一组电商评论文本。
输出：针对每条评论，输出包含各属性评分的 JSON 格式结果。确保没有属性得分为零。
输出格式示例：
{
     "quality": X,
     "warmth": Y,
     "comfort": Z,
     "softness": W,
     "preference": A,
     "repurchase_intent": B,
     "appearance": C,
     "fit": E,
     ...
}"""


async def analyze_single_comment(
    review: ProductReviewSchema,
    semaphore: asyncio.Semaphore,
    extra_metrics: str | None = None,
) -> dict | None:
    """
    单一评论分析
    """
    async with semaphore:
        start_time = time.time()
        # 通过async OpenAI与ark交互
        client = AsyncOpenAI(api_key=settings.ark_api_key, base_url=settings.ark_base_url)

        # 通过jinjia2 处理settings.ark_prompt 以替换其中的 {{extra_prompt}}
        # 允许额外的指标
        if extra_metrics:
            settings.ark_prompt = Template(settings.ark_prompt).render(extra_metrics=extra_metrics)
        else:
            settings.ark_prompt = Template(settings.ark_prompt).render()
        # log.info(f"模版语法渲染后的提示词{settings.ark_prompt}")
        try:
            response = await client.chat.completions.create(
                timeout=settings.httpx_timeout,
                model=settings.ark_model,  # 指定的模型
                messages=[
                    {"role": "system", "content": settings.ark_prompt},  # 系统角色的预设提示
                    {"role": "user", "content": review.comment},  # 用户角色的评论内容
                ],
            )
        except Exception as e:
            # 捕获并处理任何异常，打印错误信息并返回None
            print(f"Error occurred: {e}")
            return None

        end_time = time.time()

        # 从响应中获取API的使用情况信息
        usage = response.usage
        response_raw_content = response.choices[0].message.content
        log.info(response_raw_content)
        # 提取响应内容，并去除首尾空格
        # 尝试格式化输出
        try:
            response_content = json.loads(response_raw_content)
        except Exception as exc:
            log.error(f"解析LLM结果失败, 错误提示: {exc}")
            response_content = ReviewAnalysisMetrics().model_dump()

        # response_content = response.choices[0].message.content.strip()

        # 提取评分信息并转换为字典格式
        # scores = {}  # 初始化一个字典用于存储评分信息
        # for line in response_content.split(","):
        #     # 使用冒号分割每一行，分离键和值
        #     parts = line.split(":")
        #     if len(parts) == 2:  # 确保分割后有两个元素
        #         key, value = parts
        #         try:
        #             # 将值转换为浮点数并存入字典
        #             scores[key.strip()] = float(value.strip().replace("'", ""))
        #         except ValueError:
        #             print(f"Could not convert value to float: {value.strip()}")

        # 通过pydantic对象对其进行校验
        scores = ReviewAnalysisMetrics.model_validate(response_content).model_dump()

        # 返回解析的评分数据、使用情况和处理时间
        processing_time = end_time - start_time  # 计算处理总时间

        log.info(f"单一评论耗时: Task took {processing_time:.2f} seconds")

        result = {
            "review_id": review.review_id,
            "scores": scores,  # 评论的分析评分
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
            "processing_time": processing_time,
            "comment": review.comment,
        }

        return result


# 批量分析评论数据
# async def analyze_comments_batch(review: dict, analysis_results: list, extra_metrics: str | None = None):
#     comment = review.get("comment")  # 从review字典中安全获取评论文本
#     scores, usage, processing_time = await analyze_single_comment(comment, extra_metrics=extra_metrics)
#
#     analysis_results.append(
#         {
#             "review_id": review["review_id"],
#             "scores": scores,  # 评论的分析评分
#             "input_tokens": usage.prompt_tokens,
#             "output_tokens": usage.completion_tokens,
#             "processing_time": processing_time,
#             "comment": review.get("comment"),
#         }
#     )


# 汇总评论summarize分析结果
async def summarize_reviews(analyses: list):
    # 使用空格将所有分析结果中的评分信息连接成一个长字符串
    combined_analyses = " ".join([str(analysis["scores"]) for analysis in analyses])
    # 格式化汇总内容，包括所有评论的评分
    summary_content = f"以下是产品的所有评论分析: {combined_analyses}"
    client = AsyncOpenAI(api_key=settings.ark_api_key, base_url=settings.ark_base_url)

    try:
        response = await client.chat.completions.create(
            model=settings.ark_model,
            timeout=settings.httpx_timeout,
            messages=[
                {"role": "system", "content": settings.ark_summary_prompt},  # 系统角色的预设提示
                {"role": "user", "content": summary_content},  # 用户角色的汇总评论内容
            ],
        )
    except Exception as e:
        print(f"Error occurred: {e}")
        return "Summary generation failed due to an error."

    # 从响应中提取汇总结果，并去除首尾空格
    summary_result = response.choices[0].message.content.strip()
    return summary_result


# 旨在分析一组评论,通过并行处理每个评论来提高效率，并将结果汇总和记录
async def analyze_doubao(reviews: list[dict], extra_metrics: str | None = None):
    # 打印待分析的评论数量
    log.debug(f"待分析评论数量{len(reviews)}")

    start_time = time.perf_counter()
    semaphore = asyncio.Semaphore(500)
    tasks = []  # 初始化任务列表
    for review in reviews:
        # 为每条评论创建一个分析任务，并添加到任务列表
        review = ProductReviewSchema.model_validate(review)
        task = analyze_single_comment(review, semaphore=semaphore, extra_metrics=extra_metrics)
        tasks.append(task)

    # 使用 asyncio.gather 并行执行所有任务，等待所有任务完成
    results: tuple[dict | None] = await asyncio.gather(*tasks)

    total_input_tokens = 0  # 输入标记的总数
    total_output_tokens = 0  # 输出标记的总数
    total_processing_time = 0  # 总处理时间

    # 遍历每个任务的结果，累计相关统计数据
    analysis_results = []  # 用来存储每条评论分析的结果

    for res in results:
        if res:
            # print(f"{res=}")
            total_input_tokens += int(res["input_tokens"])
            total_output_tokens += int(res["output_tokens"])
            total_processing_time += float(res["processing_time"])
            analysis_results.append(res)

    total_runtime = time.perf_counter() - start_time

    summary_start = time.perf_counter()
    # 生成对所有评论的整体总结
    loop = asyncio.get_running_loop()
    start_time = loop.time()
    summary = await summarize_reviews(analysis_results)
    end_time = loop.time()
    log.info(f"总结耗时: Task took {end_time - start_time:.2f} seconds")

    total_summary_runtime = time.perf_counter() - summary_start

    # 准备将分析结果和总结以 JSON 格式保存
    output_data = {"analyses": analysis_results, "summary": summary}
    # with open("analysis_results_with_summary.json", "w", encoding="utf-8") as output_file:
    #     json.dump(output_data, output_file, ensure_ascii=False, indent=4)

    # 记录分析结果到日志
    log.debug("Analysis results have been saved to analysis_results_with_summary.json")
    log.debug(f"Total runtime: {total_runtime:.2f} seconds")
    log.debug(f"Total summary runtime: {total_summary_runtime:.2f} seconds")
    log.debug(f"Total processing time: {total_processing_time:.2f} seconds")
    log.debug(f"Total input tokens: {total_input_tokens}")
    log.debug(f"Total output tokens: {total_output_tokens}")

    # 返回分析结果和总结
    return output_data


async def main():
    # 定义产品ID和来源
    product_id, source = "866986", "gap"
    product_ids = [
        "89394973",
        "89634544",
        "90075687",
        "90129333",
        "90143622",
        "90176248",
        "90230476",
        "90253050",
        "90268462",
        "90306773",
        "90310504",
        "90354405",
        "90368246",
        "90378603",
        "90413945",
        "90528664",
        "90559291",
        "90587094",
        "90587245",
        "90596977",
        "90601051",
        "90757853",
        "90798860",
        "90872976",
        "90929496",
        "90929560",
        "90929587",
        "90946680",
        "91116005",
        "91153463",
        "91497189",
        "91530344",
        "91736623",
        "92152092",
    ]
    sources = ["target"] * len(product_ids)
    products = list(zip(product_ids, sources))
    product_id, source = random.choice(products)  # 从列表中随机取一个
    product_id, source = "89779562", "target"  # 一共600条评论, 实际有评论的235条
    # product_id, source = "795346", "gap"  # 一共3901条评论, 实际2760 条
    # 创建数据库会话
    with Session(engine) as session:
        # 构建SQL查询语句，获取特定产品ID和来源的所有评论
        stmt = select(ProductReview).where(
            cast(ColumnElement, ProductReview.product_id == product_id),
            cast(ColumnElement, ProductReview.source == source),
        )
        # 执行查询并获取结果
        reviews = session.execute(stmt).scalars().all()
        # 将查询结果中的每个评论对象转换为字典格式，方便后续处理
        review_dicts = [
            ProductReviewAnalysis.model_validate(review).model_dump(exclude_unset=True) for review in reviews
        ]
        log.debug(f"当前商品{product_id=}, 共有{len(review_dicts)}条")

    # 调用分析函数处理评论数据
    loop = asyncio.get_running_loop()
    start_time = loop.time()
    result = await analyze_doubao(reviews=review_dicts)
    end_time = loop.time()
    log.info(f"Task took {end_time - start_time:.2f} seconds")

    # 记录分析结果到日志
    log.info(result)
    print(result)


if __name__ == "__main__":
    # 读取评论文件
    # with open("review_ana/review_test.json", "r", encoding="utf-8") as file:
    #     reviews = json.load(file)

    result = asyncio.run(main())
    # result = asyncio.run(
    #     analyze_single_comment(
    #         "Love these.  They are the perfect staple pieces that will go with anything in my wardrobe.  Perfect for a capsule wardrobe."
    #     )
    # )
    print(result)
    # pprint(result)
