from fastapi import FastAPI, Depends, APIRouter
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from uvicorn import run

from api import log
from api.doubao import analyze_doubao
from api.schemas import ReviewIn, ProductReviewIn, ProductReviewAnalysis
from crawler.db import get_db
from crawler.models import ProductReview, Product

app = FastAPI()
# 设置允许跨域访问
app.add_middleware(
    CORSMiddleware,
    # allow_origins=origins,
    allow_origins=["molook.cn", "uat.molook.cn:543", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
router = APIRouter()


@app.get("/")
async def root():
    log.info("访问根目录")
    return RedirectResponse(url="/docs")


@router.post(
    "/review/analysis/haiku",
    summary="分析",
    deprecated=True,
    responses={
        200: {
            "description": "分析结果",
            "content": {
                "application/json": {
                    "example": {"product_id": "001", "source": "sourceA", "analysis_result": "分析结果示例"}
                }
            },
        }
    },
)
async def haiku_analysis(review: ReviewIn, db: Session = Depends(get_db)):
    if review.id:
        stmt = select(ProductReview).where(ProductReview.id == review.id)
    elif review.review_id and review.source:
        stmt = select(ProductReview).where(
            ProductReview.review_id == review.review_id, ProductReview.source == review.source
        )
    else:
        return {"error": "请传入id ,或review_id和source."}
    review_obj = db.execute(stmt).scalars().one_or_none()
    log.info(f"分析评论: {review_obj}")
    return review_obj


@router.post(
    "/product/review_analysis",
    summary="商品评论分析",
    responses={
        200: {
            "description": "分析结果",
            "content": {
                "application/json": {
                    "example": {
                        "analyses": [
                            {
                                "review_id": "503835754",
                                "analysis": "quality: 8, warmth: 5, comfort: 6, softness: 5, likability: 7, repurchase intent: 7, positive sentiment: 8",
                                "input_tokens": 97,
                                "output_tokens": 16,
                                "processing_time": 1.5923347473144531,
                            },
                            {
                                "review_id": "490445066",
                                "analysis": "quality: 8, warmth: 5, comfort: 7, softness: 5, likability: 7, repurchase intent: 7, positive sentiment: 8",
                                "input_tokens": 98,
                                "output_tokens": 16,
                                "processing_time": 1.6581623554229736,
                            },
                            {
                                "review_id": "505749329",
                                "analysis": "quality: 8, warmth: 7, comfort: 7, softness: 7, likability: 8, repurchase intent: 8, positive sentiment: 9",
                                "input_tokens": 96,
                                "output_tokens": 16,
                                "processing_time": 1.7821581363677979,
                            },
                            {
                                "review_id": "516109171",
                                "analysis": "quality: 7, warmth: 5, comfort: 8, softness: 7, likability: 6, repurchase intent: 5, positive sentiment: 5",
                                "input_tokens": 96,
                                "output_tokens": 16,
                                "processing_time": 1.8928513526916504,
                            },
                            {
                                "review_id": "513190270",
                                "analysis": "quality: 8, warmth: 7, comfort: 8, softness: 7, likability: 9, repurchase intent: 8, positive sentiment: 9",
                                "input_tokens": 101,
                                "output_tokens": 16,
                                "processing_time": 2.0875539779663086,
                            },
                            {
                                "review_id": "508122371",
                                "analysis": "quality: 8, warmth: 6, comfort: 7, softness: 7, likability: 8, repurchase intent: 8, positive sentiment: 8",
                                "input_tokens": 116,
                                "output_tokens": 16,
                                "processing_time": 2.1419029235839844,
                            },
                            {
                                "review_id": "501740352",
                                "analysis": "quality: 8, warmth: 6, comfort: 7, softness: 6, likability: 7, repurchase intent: 7, positive sentiment: 8",
                                "input_tokens": 101,
                                "output_tokens": 16,
                                "processing_time": 2.151305913925171,
                            },
                            {
                                "review_id": "507029223",
                                "analysis": "quality: 8, warmth: 6, comfort: 8, softness: 6, likability: 8, repurchase intent: 7, positive sentiment: 9",
                                "input_tokens": 93,
                                "output_tokens": 16,
                                "processing_time": 2.154877185821533,
                            },
                            {
                                "review_id": "507705422",
                                "analysis": "quality: 8, warmth: 5, comfort: 7, softness: 6, likability: 8, repurchase intent: 8, positive sentiment: 8",
                                "input_tokens": 113,
                                "output_tokens": 16,
                                "processing_time": 2.1589910984039307,
                            },
                            {
                                "review_id": "511518077",
                                "analysis": "quality: 8, warmth: 5, comfort: 7, softness: 5, likability: 7, repurchase intent: 7, positive sentiment: 7",
                                "input_tokens": 115,
                                "output_tokens": 16,
                                "processing_time": 2.170419931411743,
                            },
                            {
                                "review_id": "511630032",
                                "analysis": "quality: 9, warmth: 7, comfort: 8, softness: 7, likability: 8, repurchase intent: 8, positive sentiment: 8",
                                "input_tokens": 160,
                                "output_tokens": 16,
                                "processing_time": 2.219525098800659,
                            },
                            {
                                "review_id": "513459580",
                                "analysis": "quality: 7, warmth: 5, comfort: 8, softness: 6, likability: 8, repurchase intent: 7, positive sentiment: 8",
                                "input_tokens": 103,
                                "output_tokens": 16,
                                "processing_time": 2.2469570636749268,
                            },
                            {
                                "review_id": "497351171",
                                "analysis": "quality: 7, warmth: 0, comfort: 6, softness: 0, likability: 6, repurchase intent: 6, positive sentiment: 5",
                                "input_tokens": 122,
                                "output_tokens": 16,
                                "processing_time": 2.266998052597046,
                            },
                            {
                                "review_id": "510328810",
                                "analysis": "quality: 8, warmth: 6, comfort: 7, softness: 6, likability: 9, repurchase intent: 7, positive sentiment: 9",
                                "input_tokens": 103,
                                "output_tokens": 16,
                                "processing_time": 2.3023157119750977,
                            },
                            {
                                "review_id": "521547319",
                                "analysis": "quality: 8, warmth: 5, comfort: 6, softness: 5, likability: 7, repurchase intent: 7, positive sentiment: 7",
                                "input_tokens": 119,
                                "output_tokens": 16,
                                "processing_time": 2.3248939514160156,
                            },
                            {
                                "review_id": "511176409",
                                "analysis": "quality: 8, warmth: 5, comfort: 6, softness: 6, likability: 7, repurchase intent: 7, positive sentiment: 7",
                                "input_tokens": 134,
                                "output_tokens": 16,
                                "processing_time": 2.336843729019165,
                            },
                            {
                                "review_id": "513259754",
                                "analysis": "quality: 8, warmth: 7, comfort: 7, softness: 6, likability: 8, repurchase intent: 7, positive sentiment: 8",
                                "input_tokens": 101,
                                "output_tokens": 16,
                                "processing_time": 2.49733304977417,
                            },
                            {
                                "review_id": "510291900",
                                "analysis": "quality: 9, warmth: 7, comfort: 7, softness: 7, likability: 8, repurchase intent: 8, positive sentiment: 9",
                                "input_tokens": 121,
                                "output_tokens": 16,
                                "processing_time": 2.5150039196014404,
                            },
                            {
                                "review_id": "506182776",
                                "analysis": "quality: 8, warmth: 7, comfort: 9, softness: 8, likability: 9, repurchase intent: 8, positive sentiment: 9",
                                "input_tokens": 136,
                                "output_tokens": 16,
                                "processing_time": 2.628852128982544,
                            },
                            {
                                "review_id": "507273305",
                                "analysis": "quality: 7, warmth: 5, comfort: 7, softness: 5, likability: 7, repurchase intent: 7, positive sentiment: 7",
                                "input_tokens": 95,
                                "output_tokens": 16,
                                "processing_time": 2.6776041984558105,
                            },
                            {
                                "review_id": "511653232",
                                "analysis": "quality: 9, warmth: 7, comfort: 7, softness: 7, likability: 8, repurchase intent: 8, positive sentiment: 9",
                                "input_tokens": 98,
                                "output_tokens": 16,
                                "processing_time": 2.709049940109253,
                            },
                            {
                                "review_id": "513459465",
                                "analysis": "quality: 8, warmth: 5, comfort: 7, softness: 6, likability: 8, repurchase intent: 7, positive sentiment: 8",
                                "input_tokens": 98,
                                "output_tokens": 16,
                                "processing_time": 2.7234981060028076,
                            },
                            {
                                "review_id": "507277327",
                                "analysis": "quality: 8, warmth: 7, comfort: 8, softness: 7, likability: 9, repurchase intent: 8, positive sentiment: 9",
                                "input_tokens": 101,
                                "output_tokens": 16,
                                "processing_time": 2.7462518215179443,
                            },
                        ],
                        "summary": "综合这些评论分析，可以看出该产品在整体上具有较好的表现。产品质量的评分普遍较高，多数给予了 7 到 9 分的评价。在舒适度方面，平均得分较为不错，大多在 6 到 9 分之间，表明用户在使用过程中能感受到较好的舒适度。温暖程度的评价较为多样，分数在 0 到 7 之间，但总体来说处于中等水平。柔软度方面，评分集中在 5 到 7 分，表现尚可。在受人喜欢的程度、回购意愿以及正面情感方面，多数评分都在 6 到 9 分之间，反映出消费者对产品有较高的满意度和积极的态度。总体而言，该产品具有较高的质量和不错的舒适度，在温暖程度和柔软度上还有一定的提升空间，但仍受到消费者的普遍喜爱和认可，具有较好的市场前景。",
                    }
                }
            },
        }
    },
)
async def review_analysis_with_doubao(params: ProductReviewIn, db: Session = Depends(get_db)):
    """
    1. 优先从数据库查询, 如果没有则调用doubao分析;
    2. 当

    """
    stmt = select(ProductReview).where(
        ProductReview.product_id == params.product_id, ProductReview.source == params.source
    )
    reviews = db.execute(stmt).scalars().all()

    log.info(f"分析商品评论[{len(reviews)}]: {reviews}")

    # 将 ORM对象转换为字典
    review_dicts = [ProductReviewAnalysis.model_validate(review).model_dump(exclude_unset=True) for review in reviews]
    print(review_dicts)
    params.from_api = True
    if params.from_api is True:
        if params.llm == "ark":
            result = analyze_doubao(review_dicts)
        else:
            result = analyze_doubao(review_dicts)

        return dict(
            analyses=result.analyses,
            summary=result.summary,
            statistics="",
        )

    summary_stmt = select(Product.review_summary).where(
        Product.product_id == params.product_id, Product.source == params.source
    )
    summary = db.execute(summary_stmt).scalar_one_or_none()

    if summary:
        metrics_stmt = select(ProductReview.metrics).where(
            ProductReview.product_id == params.product_id, ProductReview.source == params.source
        )
        metrics = db.execute(metrics_stmt).scalar().all()
        return {"analyses": metrics, "summary": summary, "statistics": ""}
    else:
        if params.llm == "ark":
            result = analyze_doubao(review_dicts)
        else:
            result = analyze_doubao(review_dicts)
        # 将分析结果保存到数据库

        summary = result.summary
        stmt = (
            update(Product)
            .where(Product.product_id == params.product_id, Product.source == params.source)
            .values(review_summary=summary)
        )
        db.execute(stmt)
        db.commit()  # 显式提交事务

        return dict(
            analyses=result.get("analyses"),
            summary=result.get("summary"),
            statistics="",
        )

    if params.llm == "ark":
        result = analyze_doubao(review_dicts)
    else:
        result = analyze_doubao(review_dicts)

    return dict(
        analyses=result.analyses,
        summary=result.summary,
        statistics="",
    )


app.include_router(router, prefix="/api")

if __name__ == "__main__":
    run(app="api.main:app", reload=True, port=8199, host="0.0.0.0", workers=4)
    pass
