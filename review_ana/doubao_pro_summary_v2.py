import os
import json
import time
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

# 设置API密钥
api_key = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhcmstY29uc29sZSIsImV4cCI6MTcxOTg2MDA1NCwiaWF0IjoxNzE4ODYwMDU0LCJ0IjoidXNlciIsImt2IjoxLCJhaWQiOiIyMTAwMjUwMDk0IiwidWlkIjoiMCIsImlzX291dGVyX3VzZXIiOnRydWUsInJlc291cmNlX3R5cGUiOiJlbmRwb2ludCIsInJlc291cmNlX2lkcyI6WyJlcC0yMDI0MDYxODA1MzI1MC00NGdyayJdfQ.mfCjuxu1QbSkd4hWuRfAyspTCOV2bPpvNy62JhcnAr3MOkQx_KkwH0pXEc5Y-sWPU5wA55EwMfMkX-S56FNAd5Yz90zDQnmzCdOyUQiGqYLxrK7CJ4mhbOpur-1LQDFijnCG0n9pKRJpJwRbCTcWRZ6nvVRGUzcDXs-Y_itmdfUlS6fM1GUsJFcN2zyFz030VNTTQ921lvPBx2YcFHGuUNT81Gk9dOiJLxG7Fte7pNP6mCO-eCdoqzFT-ejAG2T972qBnf2iwvkdZReA9NkcL6jJBgmlnn46vOKtpkdTTEaWXBjgOPsfmhMo_C36lVBVd8cdTgcWdQde6QvAKKWT5Q"

# 设置OpenAI客户端
client = OpenAI(
    api_key=api_key,
    base_url="https://ark.cn-beijing.volces.com/api/v3"
)

# 读取评论文件
with open('review_test.json', 'r', encoding='utf-8') as file:
    reviews = json.load(file)

# 提示词
prompt_template = (
    "You are an e-commerce and sentiment analysis specialist. Analyze the customer feedback comprehensively. "
    "Provide scores for the following attributes even if not directly mentioned: product quality, warmth, comfort, "
    "softness, likability, repurchase intent, and positive sentiment. Use the maximum score of 10 for each attribute. "
    "Base your scoring on the overall sentiment if specific details are lacking. Format your response as follows: "
    "quality: X, warmth: Y, comfort: Z, softness: W, likability: A, repurchase intent: B, positive sentiment: C. "
    "Ensure no attribute is scored zero by inferring missing details from general feedback."
)

summary_prompt = (
    "You are an e-commerce and sentiment analysis specialist. Based on the following customer feedback analyses, "
    "provide a comprehensive summary analysis of the product. Mention overall product quality, comfort, and other "
    "key aspects that are frequently mentioned. Format your response as a paragraph summarizing the general sentiment "
    "and key takeaways."
)


def analyze_comments_batch(reviews_batch):
    comments = {f"评论{i + 1}": review['comment'] for i, review in enumerate(reviews_batch) if review.get("comment")}
    if not comments:
        return []

    prompt = prompt_template + "\n\n" + "\n".join([f"{key}: {value}" for key, value in comments.items()])
    start_time = time.time()

    try:
        response = client.chat.completions.create(
            model="ep-20240618053250-44grk",
            messages=[
                {"role": "system", "content": prompt}
            ]
        )
    except Exception as e:
        print(f"Error occurred: {e}")
        return []

    end_time = time.time()
    processing_time = end_time - start_time

    usage = response.usage
    response_content = response.choices[0].message.content.strip()

    # 提取评分信息并转换为字典格式
    scores = {}
    for line in response_content.split(','):
        parts = line.split(':')
        if len(parts) == 2:
            key, value = parts
            try:
                scores[key.strip()] = float(value.strip().replace("'", ""))
            except ValueError:
                print(f"Could not convert value to float: {value.strip()}")

    if not scores:
        print(f"Warning: No scores extracted for batch: {comments}")

    analysis_results = {
        "review_ids": [review["review_id"] for review in reviews_batch],
        "scores": scores,
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "processing_time": processing_time / len(comments),
        "comments": comments
    }

    return analysis_results


def summarize_reviews(analyses):
    combined_analyses = " ".join([str(analysis['scores']) for analysis in analyses])
    summary_content = f"以下是产品的所有评论分析: {combined_analyses}"

    try:
        response = client.chat.completions.create(
            model="ep-20240618053250-44grk",
            messages=[
                {"role": "system", "content": summary_prompt},
                {"role": "user", "content": summary_content}
            ]
        )
    except Exception as e:
        print(f"Error occurred: {e}")
        return "Summary generation failed due to an error."

    summary_result = response.choices[0].message.content.strip()
    return summary_result


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
        reviews_batch = reviews[i:i + batch_size]
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
output_data = {
    "analyses": analysis_results,
    "summary": summary
}
with open('analysis_results_with_summary.json', 'w', encoding='utf-8') as output_file:
    json.dump(output_data, output_file, ensure_ascii=False, indent=4)

print("Analysis results have been saved to analysis_results_with_summary.json")
print(f"Total runtime: {total_runtime:.2f} seconds")
print(f"Total processing time: {total_processing_time:.2f} seconds")
print(f"Total input tokens: {total_input_tokens}")
print(f"Total output tokens: {total_output_tokens}")
