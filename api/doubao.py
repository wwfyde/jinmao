import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI
from rich.pretty import pprint

from crawler.config import settings

summary_prompt = settings.ark_summary_prompt


def analyze_comment(review: dict):
    comment = review.get("comment")
    if not comment:
        return None

    print(f"----- Analyzing review {review['review_id']} -----")
    content = f"评论内容: {comment}"
    start_time = time.time()  # 记录开始时间
    # 创建OpenAI客户端
    client = OpenAI(
        api_key=settings.ark_api_key,
        base_url=settings.ark_base_url,
        timeout=60,
    )
    stream = client.chat.completions.create(
        model=settings.ark_model,  # 您的模型端点ID
        messages=[{"role": "system", "content": settings.ark_prompt}, {"role": "user", "content": content}],
        stream=True,
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
        "input_tokens": len(settings.ark_prompt.split()) + len(content.split()),  # 计算输入token数量
        "output_tokens": len(analysis_result.split()),  # 计算输出token数量
        "processing_time": processing_time,
    }


def summarize_reviews(analyses: list):
    combined_analyses = " ".join([analysis["analysis"] for analysis in analyses])
    summary_content = f"以下是产品的所有评论分析: {combined_analyses}"
    # 创建OpenAI客户端
    client = OpenAI(
        api_key=settings.ark_api_key,
        base_url=settings.ark_base_url,
        timeout=60,
    )
    stream = client.chat.completions.create(
        model=settings.ark_model,  # 您的模型端点ID
        messages=[
            {"role": "system", "content": settings.ark_summary_prompt},
            {"role": "user", "content": summary_content},
        ],
        stream=True,
    )

    summary_result = ""
    for chunk in stream:
        if not chunk.choices:
            continue
        summary_result += chunk.choices[0].delta.content

    return summary_result.strip()


def analyze_doubao(reviews: list[dict]) -> dict:
    """
    分析评论
    """
    start_time = time.time()  # 记录总开始时间
    # 并行处理评论分析
    analysis_results = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_processing_time = 0

    with ThreadPoolExecutor(max_workers=settings.ark_concurrency) as executor:
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

    summary = summarize_reviews(analysis_results)
    output_data = {"analyses": analysis_results, "summary": summary}
    print(total_runtime)
    return output_data


if __name__ == "__main__":
    reviews = [
        {
            "review_id": "521547319",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Quality denim",
            "comment": "Well made jeans. I ordered an 8 Slim for my son and they're still a bit big in the pelvis area but the length and quality are exceptional.",
            "nickname": "Caris, C",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 1433,
        },
        {
            "review_id": "516109171",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 3.0,
            "title": "Meh",
            "comment": "Nice feel but weird cut.",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "513459580",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Love!",
            "comment": "Love the color and they fit wonderfully on a very thin boy.",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "513459465",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Great!",
            "comment": "Great jeans for an very thin boy!",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "513259754",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "True to size",
            "comment": "Sturdy material. We know how boys are. Great fit too",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "513190270",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Awesome jeans",
            "comment": "They fit my son really nice we love gap jeans!",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "511653232",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Awesome jeans",
            "comment": "Great quality material, true to size fit.",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "511630032",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "#sweepstakes",
            "comment": "#sweepstakes\n\nThese are stable jeans. I wish gap made slim skinny jeans in different colors other than blue/black denim. Fits perfect for my slim son. Also, the quality in the denim is well worth the money! I typically purchase the jeans two sizes bigger because he grows so fast and needless to say they hold up for two school years! I do not dry his jeans at all fyi",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "511518077",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Perfect",
            "comment": "My son needed to size down in these jeans compared to the skinny jeans. I love the fit once I had the right size!!!",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "511176409",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Thank you Gap for carrying slim!",
            "comment": "My son is on the slimmer side so these slim jeans fit better than the regular version. Thank you Gap for carrying these! My only complaint would be that they would be a little more comfortable if they had more stretch in them.",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "510328810",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "My nephew loves it!",
            "comment": "Perfect for my nephew, for me it's enough that he loves it!",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "510291900",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Great fit, wash and price",
            "comment": "Great fit ~ love the slim cut so the legs are not too wide and baggy.\nNice even medium black wash.\nGreat price - can't beat it for the quality!",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "508122371",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Picky skinny-boy approved!",
            "comment": "Love these jeans for my skinny boy. Adjustable buttons in the waist but already slim so they don't look puckered even when tightened a lot.",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "507705422",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Good fit for skinny kids w/o looking like jeggings",
            "comment": "These fit my skinny kid without being too tight. The denim feels like Gap's usual good quality, too. I will get more!",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "507277327",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Great Jeans!",
            "comment": "My son love these Jean! Great color and washes well!!",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "507273305",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Love Gap.",
            "comment": "Fit good looked good.",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "507029223",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Great Purchase",
            "comment": "Perfect fit!!",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "506182776",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Excellent Quality",
            "comment": "These are the best jeans! My son is very slim and on smaller side so I love that Gap has many options with sizes. I also appreciate the waist sinch they still put in this size. They wear very well and are comfortable and fashionable!",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "505749329",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Looks great style",
            "comment": "Great purchase and the price",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "503835754",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Slim jeans",
            "comment": "Great slim jeans, not too skinny",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "501740352",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "Best jeans",
            "comment": "The best jeans for kids. True to size. Fits perfect",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "497351171",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 3.0,
            "title": "Cute but runs small",
            "comment": "Cute jeans but these run small. My 11.5 year old wears size 14 Gap jeans (he needs a 14 for the length) and these were too small overall. Need a 16.",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
        {
            "review_id": "490445066",
            "product_id": "728681",
            "source": "gap",
            "product_name": None,
            "rating": 5.0,
            "title": "True to size",
            "comment": "Fits perfect no sagging just enough room",
            "nickname": "anonymous",
            "helpful_votes": 0,
            "not_helpful_votes": 0,
            "helpful_score": 0,
        },
    ]

    start_time = time.time()
    output = analyze_doubao(reviews)
    end_time = start_time - time.time()
    print(f"Total runtime: {end_time}")
    pprint(output)
