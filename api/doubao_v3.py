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
            model=settings.ark_model,  # 指定的模型
            messages=[
                {"role": "system", "content": settings.ark_prompt},  # 系统角色的预设提示
                {"role": "user", "content": comment},                # 用户角色的评论内容
            ],
        )
    except Exception as e:
        # 捕获并处理任何异常，打印错误信息并返回None
        print(f"Error occurred: {e}")
        return None

    end_time = time.time()
    processing_time = end_time - start_time  # 计算处理总时间

    # 从响应中获取API的使用情况信息
    usage = response.usage
    # 提取响应内容，并去除首尾空格
    response_content = response.choices[0].message.content.strip()

    # 提取评分信息并转换为字典格式
    scores = {}  # 初始化一个字典用于存储评分信息
    for line in response_content.split(","):
        # 使用冒号分割每一行，分离键和值
        parts = line.split(":")
        if len(parts) == 2:  # 确保分割后有两个元素
            key, value = parts
            try:
                # 将值转换为浮点数并存入字典
                scores[key.strip()] = float(value.strip().replace("'", ""))
            except ValueError:
                print(f"Could not convert value to float: {value.strip()}")

    # 返回解析的评分数据、使用情况和处理时间
    return scores, usage, processing_time


# 批量分析评论数据
async def analyze_comments_batch(review: dict, analysis_results: list):
    comment = review.get("comment")  # 从review字典中安全获取评论文本
    scores, usage, processing_time = await analyze_single_comment(comment)

    analysis_results.append(
        {
            "review_id": review["review_id"],
            "scores": scores,  # 评论的分析评分
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
            "processing_time": processing_time,
            "comment": review.get("comment"),
        }
    )


# 汇总评论summarize分析结果
async def summarize_reviews(analyses):
    # 使用空格将所有分析结果中的评分信息连接成一个长字符串
    combined_analyses = " ".join([str(analysis["scores"]) for analysis in analyses])
    # 格式化汇总内容，包括所有评论的评分
    summary_content = f"以下是产品的所有评论分析: {combined_analyses}"
    client = AsyncOpenAI(api_key=settings.ark_api_key, base_url="https://ark.cn-beijing.volces.com/api/v3")

    try:
        response = await client.chat.completions.create(
            model="ep-20240618053250-44grk",
            messages=[
                {"role": "system", "content": settings.ark_summary_prompt},  # 系统角色的预设提示
                {"role": "user", "content": summary_content},                # 用户角色的汇总评论内容
            ],
        )
    except Exception as e:
        print(f"Error occurred: {e}")
        return "Summary generation failed due to an error."

    # 从响应中提取汇总结果，并去除首尾空格
    summary_result = response.choices[0].message.content.strip()
    return summary_result


# 旨在分析一组评论,通过并行处理每个评论来提高效率，并将结果汇总和记录
async def analyze_doubao(reviews: list[dict]):
    # 打印待分析的评论数量
    print(len(reviews))

    analysis_results = []  # 用来存储每条评论分析的结果
    start_time = time.perf_counter()

    tasks = [] # 初始化任务列表
    for review in reviews:
        # 为每条评论创建一个分析任务，并添加到任务列表
        task = analyze_comments_batch(review, analysis_results)
        tasks.append(task)

    # 使用 asyncio.gather 并行执行所有任务，等待所有任务完成
    results = await asyncio.gather(*tasks)

    total_input_tokens = 0  # 输入标记的总数
    total_output_tokens = 0  # 输出标记的总数
    total_processing_time = 0 # 总处理时间

    # 遍历每个任务的结果，累计相关统计数据
    for res in results:
        if res:
            print(f"{res=}")
            total_input_tokens += res["input_tokens"]
            total_output_tokens += res["output_tokens"]
            total_processing_time += res["processing_time"]

    total_runtime = time.perf_counter() - start_time

    summary_start = time.perf_counter()
    # 生成对所有评论的整体总结
    summary = await summarize_reviews(analysis_results)

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

    # 创建数据库会话
    with Session(engine) as session:
        # 构建SQL查询语句，获取特定产品ID和来源的所有评论
        stmt = select(ProductReview).where(ProductReview.product_id == product_id, ProductReview.source == source)
        # 执行查询并获取结果
        reviews = session.execute(stmt).scalars().all()
        # 将查询结果中的每个评论对象转换为字典格式，方便后续处理
        review_dicts = [
            ProductReviewAnalysis.model_validate(review).model_dump(exclude_unset=True) for review in reviews
        ]

    # 调用分析函数处理评论数据
    result = await analyze_doubao(reviews=review_dicts)
    # 记录分析结果到日志
    log.info(result)
    print(result)


if __name__ == "__main__":
    # 读取评论文件
    # with open("review_ana/review_test.json", "r", encoding="utf-8") as file:
    #     reviews = json.load(file)

    # asyncio.run(main())
    result = asyncio.run(analyze_single_comment(
        'Love these.  They are the perfect staple pieces that will go with anything in my wardrobe.  Perfect for a capsule wardrobe.'))
    print(result)
