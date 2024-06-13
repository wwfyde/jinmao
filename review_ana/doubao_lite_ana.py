import os
import json
import time
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

# 设置API密钥
os.environ["ARK_API_KEY"] = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhcmstY29uc29sZSIsImV4cCI6MTcxOTA3NjM4MiwiaWF0IjoxNzE4MDc2MzgyLCJ0IjoidXNlciIsImt2IjoxLCJhaWQiOiIyMTAwMjUwMDk0IiwidWlkIjoiMCIsImlzX291dGVyX3VzZXIiOnRydWUsInJlc291cmNlX3R5cGUiOiJlbmRwb2ludCIsInJlc291cmNlX2lkcyI6WyJlcC0yMDI0MDYxMTAyMDMxNi1naDVwaCJdfQ.hoVIRqoo1b3TKZzs9s8x0Jy7nJ-mDvvDdTKi8scs4IopIhX10YjVVhBhE8WSE19VLfDRrhvOv2pSeQQgkIH1J8R0zU1pZENLoUQ8txcE67In134v2TdTvNm8vgJ8vLRBT_nf7VeFizJaXZU4IlgMcapxDbveCyKpUKqkJKivyG6mZd1ybQaOm5fB0RbQtLd1nDyUNZyE9OhhXG69yEumEMr-_0q8EtXtnLm0yz6tf43RRkKhbn72JCfuN_J7nNow07PujF2hvfubiMCDo-Ko9YwU1nvjAkH9ZqHxDhl0oK3jlh1ONXbYCZEbgRm3FBCf7A-2UqldUN2NyCRjyHds6A"

# 从环境变量中获取API密钥
api_key = os.environ.get("ARK_API_KEY")
if not api_key:
    raise ValueError("API key not found. Please set the 'ARK_API_KEY' environment variable.")

# 创建OpenAI客户端
client = OpenAI(
    api_key=api_key,
    base_url="https://ark.cn-beijing.volces.com/api/v3",
)

# 读取评论文件
with open('reviews500.json', 'r') as file:
    reviews = json.load(file)

# 提示词
prompt = (
    "You are an e-commerce and sentiment analysis specialist. Analyze the customer feedback comprehensively. "
    "Provide scores for the following attributes even if not directly mentioned: product quality, warmth, comfort, "
    "softness, likability, repurchase intent, and positive sentiment. Use the maximum score of 10 for each attribute. "
    "Base your scoring on the overall sentiment if specific details are lacking. Format your response as follows: "
    "quality: X, warmth: Y, comfort: Z, softness: W, likability: A, repurchase intent: B, positive sentiment: C. "
    "Ensure no attribute is scored zero by inferring missing details from general feedback."
)

def analyze_comment(review):
    comment = review.get("comment")
    if not comment:
        return None

    print(f"----- Analyzing review {review['review_id']} -----")
    content = f"评论内容: {comment}"
    start_time = time.time()  # 记录开始时间
    stream = client.chat.completions.create(
        model="ep-20240611020316-gh5ph",  # 您的模型端点ID
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": content}
        ],
        stream=True
    )

    analysis_result = ""
    for chunk in stream:
        if not chunk.choices:
            continue
        analysis_result += chunk.choices[0].delta.content

    end_time = time.time()  # 记录结束时间
    processing_time = end_time - start_time

    return {
        "review_id": review["review_id"],
        "analysis": analysis_result.strip(),
        "input_tokens": len(prompt.split()) + len(content.split()),  # 计算输入token数量
        "output_tokens": len(analysis_result.split()),  # 计算输出token数量
        "processing_time": processing_time
    }

# 并行处理评论分析
analysis_results = []
total_input_tokens = 0
total_output_tokens = 0
total_processing_time = 0

start_time = time.time()  # 记录总开始时间

with ThreadPoolExecutor(max_workers=10) as executor:
    future_to_review = {executor.submit(analyze_comment, review): review for review in reviews}
    for future in as_completed(future_to_review):
        result = future.result()
        if result:
            analysis_results.append(result)
            total_input_tokens += result["input_tokens"]
            total_output_tokens += result["output_tokens"]
            total_processing_time += result["processing_time"]

end_time = time.time()  # 记录总结束时间
total_runtime = end_time - start_time

# 将分析结果保存为JSON文件
with open('analysis_results.json', 'w', encoding='utf-8') as output_file:
    json.dump(analysis_results, output_file, ensure_ascii=False, indent=4)

print("Analysis results have been saved to analysis_results.json")
print(f"Total runtime: {total_runtime:.2f} seconds")
print(f"Total processing time: {total_processing_time:.2f} seconds")
print(f"Total input tokens: {total_input_tokens}")
print(f"Total output tokens: {total_output_tokens}")
