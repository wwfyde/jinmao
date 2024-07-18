import asyncio
import json
import logging
import random
import re
import time
from typing import cast

import tiktoken
from jinja2 import Template
from openai import AsyncOpenAI
from sqlalchemy import select, ColumnElement
from sqlalchemy.orm import Session

from crawler.config import settings
from crawler.db import engine
from crawler.models import ProductReview
from jinmao_api import log
from jinmao_api.schemas import ProductReviewAnalysisValidator, ReviewAnalysisMetrics, ProductReviewSchema

# crawler_logger = logging.getLogger("crawler")
# crawler_logger.setLevel(logging.INFO)
log_libraries = ["httpx", "httpcore", "openai"]
for library in log_libraries:
    library_logger = logging.getLogger(library)
    library_logger.setLevel(logging.WARN)


async def analyze_single_comment(
        review: ProductReviewSchema,
        semaphore: asyncio.Semaphore,
        extra_metrics: list[str] | str | None = None,
) -> dict | None:
    """
    单一评论分析
    """
    async with semaphore:
        start_time = time.time()
        # 通过async OpenAI与ark交互
        client = AsyncOpenAI(api_key=settings.ark_doubao.api_key, base_url=settings.ark_doubao.base_url)

        # 通过jinjia2 处理settings.ark_prompt 以替换其中的 {{extra_prompt}}
        # 允许额外的指标
        if isinstance(extra_metrics, list):
            extra_metrics_str = ", ".join(extra_metrics)
            extra_metrics_str = re.sub("([A-Z]+)", r"_\1", extra_metrics_str)

            extra_metrics_str = re.sub("([A-Z][a-z]+)", r"_\1", extra_metrics_str)
            extra_metrics_str = extra_metrics_str.replace("-", "_").strip(" _")
        if extra_metrics:
            prompt = Template(settings.ark_extra_metrics_prompt).render(extra_metrics=extra_metrics,
                                                                        extra_metrics_str=extra_metrics_str,
                                                                        random=random
                                                                        )
        else:
            prompt = settings.ark_prompt
        # log.info(f"模版语法渲染后的提示词{prompt=}")

        # log.info(f"用户评论内容: {review.comment}")
        try:
            response = await client.chat.completions.create(
                timeout=settings.httpx_timeout,
                model=settings.ark_doubao.model,  # 指定的模型
                messages=[
                    {"role": "system", "content": prompt},  # 系统角色的预设提示
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
        # log.debug(response_raw_content)
        # 提取响应内容，并去除首尾空格
        # 尝试格式化输出
        try:
            response_content = json.loads(response_raw_content)
        except Exception as exc:
            log.error(f"解析LLM结果失败, 错误提示: {exc}")

            # 解析失败时对指标分数进行置零
            response_content = ReviewAnalysisMetrics().model_dump(exclude_unset=True)

        # 通过pydantic对象对其进行校验
        scores = ReviewAnalysisMetrics.model_validate(response_content).model_dump(exclude_unset=True)

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


# 汇总评论summarize分析结果
async def summarize_reviews(reviews: list) -> dict:
    """
    使用空格将所有分析结果中的评分信息连接成一个长字符串
    combined_analyses = " ".join([str(analysis["scores"]) for analysis in reviews])
    格式化汇总内容，包括所有评论的评分

    从评论中获取
    """
    loop = asyncio.get_running_loop()
    start_time = loop.time()
    # 提取评论
    comments = []
    comments_str = ""
    totoal_str = 0
    for review in reviews:
        comment = review.get("comment", "")
        if len(comment) >= 1024:
            comment = comment[:1024]
        totoal_str += len(comment)
        comments_str += comment + "\n"
        enc = tiktoken.encoding_for_model("gpt-4")
        tokens = enc.encode(comments_str)
        if len(tokens) >= 1024 * 28:
            break
        comments.append(comment)

    summary_content = f"{comments_str}"

    client = AsyncOpenAI(api_key=settings.ark_doubao.api_key, base_url=settings.ark_doubao.base_url)

    try:
        response = await client.chat.completions.create(
            model=settings.ark_doubao.model,
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
    usage = response.usage
    log.info(
        f"【评论总结接口】总字符串: {len(comments_str)},  用户输入token:{usage.prompt_tokens}, 输出token: {usage.completion_tokens}, 总计token: {usage.total_tokens}"
    )
    summary_result = response.choices[0].message.content.strip()
    end_time = loop.time()
    log.info(f"评论总结耗时: Task took {end_time - start_time:.2f} seconds")
    try:
        summary_result = json.loads(summary_result)
    except Exception as e:
        log.warning(f"解析LLM结果失败, 错误提示: {e}")
        summary_result = {
            "zh": "评论总结失败, 请重试",
            "en": "Summary generation failed, please try again",
        }

    return summary_result


# 旨在分析一组评论,通过并行处理每个评论来提高效率，并将结果汇总和记录
async def analyze_reviews(reviews: list[dict], extra_metrics: list[str] | str | None = None) -> list[dict | None]:
    """
    分析商品所有评论
    """
    # 打印待分析的评论数量
    log.debug(f"待分析评论数量{len(reviews)}")
    loop = asyncio.get_running_loop()
    start_time = loop.time()

    semaphore = asyncio.Semaphore(settings.review_analysis_concurrency)
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

    # 统计总的评论分析耗时
    for res in results:
        if res:
            # print(f"{res=}")
            total_input_tokens += int(res["input_tokens"])
            total_output_tokens += int(res["output_tokens"])
            total_processing_time += float(res["processing_time"])
            analysis_results.append(res)

    # 记录分析结果到日志
    log.info(f"Total processing time: {total_processing_time:.2f} seconds")
    log.info(f"Total input tokens: {total_input_tokens}")
    log.info(f"Total output tokens: {total_output_tokens}")

    end_time = loop.time()
    log.info(f"评论分析耗时: Task took {end_time - start_time:.2f} seconds")
    # 返回分析结果和总结
    return analysis_results


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
    # product_id, source = "89779562", "target"  # 一共600条评论, 实际有评论的235条
    # product_id, source = "795346", "gap"  # 一共3901条评论, 实际2760 条

    # 创建数据库会话 并从数据库中拉取商品所有评论
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
            ProductReviewAnalysisValidator.model_validate(review).model_dump(exclude_unset=True) for review in reviews
        ]
        log.debug(f"当前商品{product_id=}, 共有{len(review_dicts)}条")
    if not review_dicts:
        return

    # 并发处理评论分析和评论总结
    async with asyncio.TaskGroup() as tg:
        analysis_task = tg.create_task(analyze_reviews(reviews=review_dicts,
                                                       ))
        summary_task = tg.create_task(
            summarize_reviews(
                reviews=review_dicts,
            )
        )
        single_analysis_task = tg.create_task(
            analyze_single_comment(
                ProductReviewSchema.model_validate(random.choice(review_dicts)),
                semaphore=asyncio.Semaphore(1),
                extra_metrics=["性价比", "soft"],
            )
        )
        analysis_task.add_done_callback(lambda fut: print(f"评论分析完成: {fut.result()}"))
        summary_task.add_done_callback(lambda fut: print(f"评论总结完成: {fut.result()}"))
        single_analysis_task.add_done_callback(lambda fut: print(f"单一评论分析完成: {fut.result()}"))


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
    # print(result)
    # pprint(result)
