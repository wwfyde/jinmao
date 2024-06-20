import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from IPython.lib.pretty import pprint
from openai import OpenAI

from crawler import log
from crawler.config import settings


# from openai import AsyncOpenAI


def analyze_comments_batch(reviews_batch):
    """
    批量分析评论
    """
    comments = {f"评论{i + 1}": review["comment"] for i, review in enumerate(reviews_batch) if review.get("comment")}
    if not comments:
        return []
    prompt_template = settings.ark_prompt
    prompt = prompt_template + "\n\n" + "\n".join([f"{key}: {value}" for key, value in comments.items()])
    start_time = time.time()
    client = OpenAI(
        api_key=settings.ark_api_key,
        base_url=settings.ark_base_url,
    )

    try:
        response = client.chat.completions.create(
            model="ep-20240618053250-44grk", messages=[{"role": "system", "content": prompt}]
        )
    except Exception as e:
        log.debug(f"Error occurred: {e}")
        return []

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
                log.debug(f"Could not convert value to float: {value.strip()}")

    if not scores:
        log.debug(f"Warning: No scores extracted for batch: {comments}")

    analysis_results = {
        "review_ids": [review["review_id"] for review in reviews_batch],
        "scores": scores,
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "processing_time": processing_time / len(comments),
        "comments": comments,
    }

    return analysis_results


def summarize_reviews(analyses):
    combined_analyses = " ".join([str(analysis["scores"]) for analysis in analyses])
    summary_content = f"以下是产品的所有评论分析: {combined_analyses}"
    client = OpenAI(
        api_key=settings.ark_api_key,
        base_url=settings.ark_base_url,
    )
    try:
        response = client.chat.completions.create(
            model="ep-20240618053250-44grk",
            messages=[
                {"role": "system", "content": settings.ark_summary_prompt},
                {"role": "user", "content": summary_content},
            ],
        )
    except Exception as e:
        log.debug(f"Error occurred: {e}")
        return "Summary generation failed due to an error."

    summary_result = response.choices[0].message.content.strip()
    return summary_result


def analyze_doubao(reviews: list[dict]):
    # 并行处理评论分析
    batch_size = 1  # 每次处理一个评论，以提高并行度
    analysis_results = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_processing_time = 0

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=200) as executor:  # 增加最大工作线程数
        futures = []
        for i in range(0, len(reviews), batch_size):
            reviews_batch = reviews[i : i + batch_size]
            futures.append(executor.submit(analyze_comments_batch, reviews_batch))

        for future in as_completed(futures):
            result = future.result()
            if result:
                analysis_results.append(result)
                total_input_tokens += result["input_tokens"]
                total_output_tokens += result["output_tokens"]
                total_processing_time += result["processing_time"]

    end_time = time.time()
    total_runtime = end_time - start_time

    # 生成整体总结
    summary = summarize_reviews(analysis_results)

    # 将分析结果保存为JSON文件
    output_data = {"analyses": analysis_results, "summary": summary}
    with open("analysis_results_with_summary.json", "w", encoding="utf-8") as output_file:
        json.dump(output_data, output_file, ensure_ascii=False, indent=4)

    log.debug("Analysis results have been saved to analysis_results_with_summary.json")
    log.debug(f"Total runtime: {total_runtime:.2f} seconds")
    log.debug(f"Total processing time: {total_processing_time:.2f} seconds")
    log.debug(f"Total input tokens: {total_input_tokens}")
    log.debug(f"Total output tokens: {total_output_tokens}")

    return output_data


if __name__ == "__main__":
    # 读取评论文件
    with open("review_test.json", "r", encoding="utf-8") as file:
        reviews = json.load(file)
    result = analyze_doubao(reviews=reviews)
    log.info(result)
    pprint(result)
