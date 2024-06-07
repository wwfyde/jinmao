import json
import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

access_key = os.getenv("AKLTYTZiYjE5ZTZjZjkzNDZjNDg0ZDk5MTQ3NmRhNWM4YzA")
secret_key = os.getenv("T0dRNE9XTTJZakZpTkRjMU5EVXlaRGt6TTJSbFlXRmtNV1psWTJSaU1ESQ==")
if not access_key or not secret_key:
    raise ValueError("API keys are not set in environment variables")

# 设置 API 端点和头信息
api_url = 'https://maas-api.ml-platform-cn-beijing.volces.com'
headers = {
    'Content-Type': 'application/json',
    'AccessKeyId': access_key,
    'SecretAccessKey': secret_key
}

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
        "Base your scoring on the overall sentiment if specific details are lacking."
    )

def analyze_single_comment(comment, prompt):
    req = {
        "model": {"name": "skylark-chat"},
        "parameters": {
            "max_new_tokens": 1000,
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 0,
        },
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": comment['comment']}
        ]
    }
    try:
        response = requests.post(api_url, headers=headers, data=json.dumps(req))
        response.raise_for_status()
        response_content = response.json()['choices'][0]['message']['content']
        scores = extract_scores(response_content)
        result = {
            'review_id': comment['review_id'],
            'comment': comment['comment'],
            'scores': scores
        }
        return result
    except requests.RequestException as e:
        print(f"Failed to retrieve message content for comment: {comment['comment']}")
        print(e)
        return None

def analyze_comments(comments, prompt, max_workers=10):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
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
    for part in parts:
        if ':' in part:
            key, value = part.split(':', 1)
            key = key.strip().lower()
            value = re.sub(r"[^\d.]", "", value.strip())
            try:
                if value.count('.') <= 1:
                    value = round(float(value), 1)
                    if key in scores and value is not None:
                        scores[key] = value
            except ValueError:
                print(f"Invalid value for {key}: {value}")
    return scores

def save_results_to_json(results, output_file):
    try:
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(results, file, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Failed to save results to {output_file}: {e}")

def main():
    file_path = "comments.json"
    output_file = "predicted_scores.json"
    comments = load_comments(file_path)
    prompt = prepare_prompt()
    results = analyze_comments(comments, prompt, max_workers=20)  # 调整 max_workers 以增加并行处理数量
    save_results_to_json(results, output_file)

if __name__ == "__main__":
    main()
