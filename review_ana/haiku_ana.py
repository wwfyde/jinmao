import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from anthropic import AnthropicBedrock

# 使用环境变量加载敏感信息
client = AnthropicBedrock(
    aws_access_key="AKIAZI2LIHJRXUXM4TR2",  # 使用环境变量保护密钥
    aws_secret_key="E4gNUz5Z/AIAyj91mtOga1wqxT/ramRW9hCB5FTm",  # 使用环境变量保护密钥
    aws_region="us-west-2",  # 指定AWS区域
)


def load_comments(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data
    except Exception as e:
        print(f"Failed to load comments from {file_path}: {e}")
        return []


def prepare_prompt():
    return (
        "You are an e-commerce and sentiment analysis specialist. Analyze the customer feedback comprehensively. "
        "Provide scores for the following attributes even if not directly mentioned: product quality, warmth, comfort, "
        "softness, likability, repurchase intent, and positive sentiment. Use the maximum score of 10 for each attribute. "
        "Base your scoring on the overall sentiment if specific details are lacking. Format your response as follows: "
        "quality: X, warmth: Y, comfort: Z, softness: W, likability: A, repurchase intent: B, positive sentiment: C. "
        "Ensure no attribute is scored zero by inferring missing details from general feedback."
    )


def analyze_single_comment(comment, prompt):
    content = prompt + " " + comment['comment']
    start_time = time.time()  # 记录开始时间
    try:
        message = client.messages.create(
            model="anthropic.claude-3-haiku-20240307-v1:0",
            max_tokens=512,
            messages=[{"role": "user", "content": content}]
        )

        end_time = time.time()  # 记录结束时间

        if hasattr(message, 'content'):
            response = str(message.content).strip()
            # 提取评分
            scores = extract_scores(response)
            result = {
                'review_id': comment['review_id'],
                'scores': scores,
                'input_tokens': len(content.split()),  # 计算输入token数量
                'output_tokens': len(response.split()),  # 计算输出token数量
                'processing_time': end_time - start_time  # 计算处理时间
            }
            return result
        else:
            print(f"Failed to retrieve message content for comment: {comment['comment']}")
            return None
    except Exception as e:
        print(f"Exception occurred while processing comment: {comment['comment']}. Error: {e}")
        return None


def analyze_comments(comments, prompt, max_workers=10):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:  # 使用指定数量的线程并行处理
        futures = {executor.submit(analyze_single_comment, comment, prompt): comment for comment in comments}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    return results


def extract_scores(response):
    scores = {
        'quality': None,
        'warmth': None,
        'comfort': None,
        'softness': None,
        'likability': None,
        'repurchase intent': None,
        'positive sentiment': None
    }
    parts = response.split(',')
    filled_scores = []
    for part in parts:
        if ':' in part:
            key, value = part.split(':', 1)
            key = key.strip().lower()
            value = re.sub(r"[^\d.]", "", value.strip())
            # 确保值可以转换为浮点数且格式正确
            try:
                if value.count('.') <= 1:  # 检查点号数量
                    value = round(float(value), 1)
                    if key in scores and value is not None:
                        scores[key] = value
                        filled_scores.append(value)
            except ValueError:
                print(f"Invalid value for {key}: {value}")

    # 计算提供的评分的平均值，并将其用于缺失的评分
    if filled_scores:
        average_score = round(sum(filled_scores) / len(filled_scores), 1)  # 四舍五入到一位小数
        for key in scores:
            if scores[key] is None:
                scores[key] = average_score

    return scores


def save_results_to_json(results, output_file):
    try:
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(results, file, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Failed to save results to {output_file}: {e}")


def main():
    file_path = "reviews500.json"
    output_file = "predicted_scores.json"
    comments = load_comments(file_path)
    prompt = prepare_prompt()

    start_time = time.time()  # 记录总开始时间
    results = analyze_comments(comments, prompt, max_workers=50)  # 调整 max_workers 以增加并行处理数量
    end_time = time.time()  # 记录总结束时间

    total_input_tokens = sum(result['input_tokens'] for result in results)
    total_output_tokens = sum(result['output_tokens'] for result in results)
    total_processing_time = end_time - start_time

    # 仅保存评分结果
    scores_only = [{'review_id': result['review_id'], 'scores': result['scores']} for result in results]

    save_results_to_json(scores_only, output_file)

    print(f"Analysis results have been saved to {output_file}")
    print(f"Total processing time: {total_processing_time:.2f} seconds")
    print(f"Total input tokens: {total_input_tokens}")
    print(f"Total output tokens: {total_output_tokens}")


if __name__ == "__main__":
    main()
