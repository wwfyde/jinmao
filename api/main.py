import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from anthropic import AnthropicBedrock
from fastapi import FastAPI
from pydantic import BaseModel
from starlette.responses import RedirectResponse

from api import log

app = FastAPI()

client = AnthropicBedrock(
    aws_access_key="AKIAZI2LIHJRXUXM4TR2",  # 使用环境变量保护密钥
    aws_secret_key="E4gNUz5Z/AIAyj91mtOga1wqxT/ramRW9hCB5FTm",  # 使用环境变量保护密钥
    aws_region="us-west-2",  # 指定AWS区域
)


class ReviewIn(BaseModel):
    review_id: str
    id: str | None = None
    comment: str
    source: str


def load_comments(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
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
    content = prompt + " " + comment["comment"]
    try:
        message = client.messages.create(
            model="anthropic.claude-3-haiku-20240307-v1:0",
            max_tokens=512,
            messages=[{"role": "user", "content": content}],
        )

        if hasattr(message, "content"):
            response = str(message.content).strip()
            # 提取评分
            scores = extract_scores(response)
            result = {"review_id": comment["review_id"], "comment": comment["comment"], "scores": scores}
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
        "quality": None,
        "warmth": None,
        "comfort": None,
        "softness": None,
        "likability": None,
        "repurchase intent": None,
        "positive sentiment": None,
    }
    parts = response.split(",")
    filled_scores = []
    for part in parts:
        if ":" in part:
            key, value = part.split(":", 1)
            key = key.strip().lower()
            value = re.sub(r"[^\d.]", "", value.strip())
            # 确保值可以转换为浮点数且格式正确
            try:
                if value.count(".") <= 1:  # 检查点号数量
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
        with open(output_file, "w", encoding="utf-8") as file:
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


@app.get("/")
async def root():
    log.info("访问根目录")
    return RedirectResponse(url="/docs")


@app.post("/analysis/haiku", summary="诗歌分析")
async def haiku_analysis():
    return {"message": "Hello World"}


if __name__ == "__main__":
    # run(app="api.main:app", reload=True, port=8199, workers=4)
    main()
