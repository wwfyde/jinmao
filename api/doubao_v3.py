import asyncio
import time

from IPython.lib.pretty import pprint
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas import ProductReviewAnalysis
from crawler import log
from crawler.config import settings
from crawler.db import engine
from crawler.models import ProductReview


# 设置API密钥

# 设置OpenAI客户端


async def analyze_single_comment(comment: str):
    """
    单一评论分析
    """
    start_time = time.time()
    # 通过async OpenAI与ark交互
    client = AsyncOpenAI(api_key=settings.ark_api_key, base_url=settings.ark_base_url)

    try:
        response = await client.chat.completions.create(
            model=settings.ark_model,
            messages=[
                {"role": "system", "content": settings.ark_prompt},
                {"role": "user", "content": comment},
            ],
        )
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

    end_time = time.time()
    processing_time = end_time - start_time

    usage = response.usage
    response_content = response.choices[0].message.content.strip()

    # 提取评分信息并转换为字典格式
    scores = {}
    for line in response_content.split(","):
        parts = line.split(":")
        if len(parts) == 2:
            key, value = parts
            try:
                scores[key.strip()] = float(value.strip().replace("'", ""))
            except ValueError:
                print(f"Could not convert value to float: {value.strip()}")

    return scores, usage, processing_time


async def analyze_comments_batch(review: dict, analysis_results: list):
    comment = review.get("comment")
    scores, usage, processing_time = await analyze_single_comment(comment)

    analysis_results.append(
        {
            "review_id": review["review_id"],
            "scores": scores,
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
            "processing_time": processing_time,
            "comment": review.get("comment"),
        }
    )


async def summarize_reviews(analyses):
    combined_analyses = " ".join([str(analysis["scores"]) for analysis in analyses])
    summary_content = f"以下是产品的所有评论分析: {combined_analyses}"
    client = AsyncOpenAI(api_key=settings.ark_api_key, base_url="https://ark.cn-beijing.volces.com/api/v3")

    try:
        response = await client.chat.completions.create(
            model="ep-20240618053250-44grk",
            messages=[
                {"role": "system", "content": settings.ark_summary_prompt},
                {"role": "user", "content": summary_content},
            ],
        )
    except Exception as e:
        print(f"Error occurred: {e}")
        return "Summary generation failed due to an error."

    summary_result = response.choices[0].message.content.strip()
    return summary_result


async def analyze_doubao(reviews: list[dict]):
    # 并行处理评论分析
    print(len(reviews))

    analysis_results = []
    start_time = time.perf_counter()

    tasks = []
    for review in reviews:
        task = analyze_comments_batch(review, analysis_results)
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    total_input_tokens = 0
    total_output_tokens = 0
    total_processing_time = 0

    for res in results:
        if res:
            print(f"{res=}")
            total_input_tokens += res["input_tokens"]
            total_output_tokens += res["output_tokens"]
            total_processing_time += res["processing_time"]

    total_runtime = time.perf_counter() - start_time

    summary_start = time.perf_counter()
    # 生成整体总结
    summary = await summarize_reviews(analysis_results)

    total_summary_runtime = time.perf_counter() - summary_start

    # 将分析结果保存为JSON文件
    output_data = {"analyses": analysis_results, "summary": summary}
    # with open("analysis_results_with_summary.json", "w", encoding="utf-8") as output_file:
    #     json.dump(output_data, output_file, ensure_ascii=False, indent=4)

    log.debug("Analysis results have been saved to analysis_results_with_summary.json")
    log.debug(f"Total runtime: {total_runtime:.2f} seconds")
    log.debug(f"Total summary runtime: {total_summary_runtime:.2f} seconds")
    log.debug(f"Total processing time: {total_processing_time:.2f} seconds")
    log.debug(f"Total input tokens: {total_input_tokens}")
    log.debug(f"Total output tokens: {total_output_tokens}")

    return output_data


async def main():
    product_id, source = "866986", "gap"

    with Session(engine) as session:
        stmt = select(ProductReview).where(ProductReview.product_id == product_id, ProductReview.source == source)
        reviews = session.execute(stmt).scalars().all()
        review_dicts = [
            ProductReviewAnalysis.model_validate(review).model_dump(exclude_unset=True) for review in reviews
        ]

    result = await analyze_doubao(reviews=review_dicts)
    log.info(result)
    pprint(result)


if __name__ == "__main__":
    # 读取评论文件
    # with open("review_ana/review_test.json", "r", encoding="utf-8") as file:
    #     reviews = json.load(file)

    asyncio.run(main())
