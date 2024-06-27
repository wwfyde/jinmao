from typing import cast

from fastapi import FastAPI, Depends, APIRouter
from sqlalchemy import select, ColumnElement
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from uvicorn import run

from api import log
from api.doubao_v3 import analyze_doubao
from api.schemas import (
    ReviewIn,
    ProductReviewIn,
    ProductReviewAnalysis,
    APIAnalysisResult,
    ProductReviewAnalysisByMetricsIn,
)
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
async def haiku_analysis(
    review: ReviewIn,
    db: Session = Depends(get_db),
):
    if review.id:
        stmt = select(ProductReview).where(cast(ColumnElement, ProductReview.id == review.id))
    elif review.review_id and review.source:
        stmt = select(ProductReview).where(
            cast(ColumnElement, ProductReview.review_id == review.review_id),
            cast(ColumnElement, ProductReview.source == review.source),
        )
    else:
        return {"error": "请传入id ,或review_id和source."}
    review_obj = db.execute(stmt).scalars().one_or_none()
    log.info(f"分析评论: {review_obj}")
    return review_obj


@router.post(
    "/product/review_analysis",
    summary="商品评论分析",
)
async def review_analysis(params: ProductReviewIn, db: Session = Depends(get_db)):
    """
    1. 优先从数据库查询, 如果没有则调用doubao分析;
    2. 当
     评论总数
     指标项: 大于等于阈值的评论数
     每个指标的得分和数量, 质量好占比/总评论数

    """
    stmt = select(ProductReview).where(
        cast(ColumnElement, ProductReview.product_id == params.product_id),
        cast(ColumnElement, ProductReview.source == params.source),
    )
    reviews = db.execute(stmt).scalars().all()

    log.info(f"分析商品评论[{len(reviews)}]: {reviews}")

    # 将 ORM对象转换为字典
    review_dicts = [ProductReviewAnalysis.model_validate(review).model_dump(exclude_unset=True) for review in reviews]
    log.debug(review_dicts)

    # 查询商品信息
    stmt = select(Product).where(
        cast(ColumnElement, Product.product_id == params.product_id),
        cast(ColumnElement, Product.source == params.source),
    )
    product_db = db.execute(stmt).scalars().one_or_none()
    # 通过redis 设置商品分析结果缓存, 超过7天自动重新分析
    if isinstance(params.extra_metrics, list):
        params.extra_metrics = ", ".join(params.extra_metrics)
    if not product_db.is_review_analyzed or params.from_api is True:
        if params.llm == "ark":
            result = await analyze_doubao(review_dicts, params.extra_metrics)
        else:
            result = await analyze_doubao(review_dicts, params.extra_metrics)
        # 将分析结果保存到数据库
        result = APIAnalysisResult.model_validate(result)
        summary = result.summary

        # stmt = (
        #     update(Product)
        #     .where(Product.product_id == params.product_id, Product.source == params.source)  # noqa
        #     .values(review_summary=summary, is_review_analyzed=True)
        # )
        # db.execute(stmt)
        product_db.is_review_analyzed = True
        product_db.review_summary = summary
        product_db.review_analyses = result.analyses
        db.commit()  # 显式提交事务

        # 获取空间数据
        if result.analyses is not None:
            total_reviews = len(result.analyses)
            metrics_counts = {}
            for item in result.analyses:
                for key, value in item.get("scores", {}).items():
                    if float(value) >= 5:
                        if key not in metrics_counts:
                            metrics_counts[key] = dict(count=0)
                        metrics_counts[key]["count"] += 1

            for key, value in metrics_counts:
                metrics_counts[key]["ratio"] = f'{round(metrics_counts[key]["count"] / total_reviews * 100)}%'
                metrics_counts[key]["total"] = total_reviews

        else:
            metrics_counts = {}
        result.statistics = metrics_counts
        log.debug(result.statistics)
        return result
    else:
        # metrics_stmt = select(ProductReview.metrics).where(
        #     cast(ColumnElement, ProductReview.product_id == params.product_id),
        #     cast(ColumnElement, ProductReview.source == params.source),
        # )
        # metrics = db.execute(metrics_stmt).scalar().all()
        if product_db.review_analyses is not None:
            total_reviews = len(product_db.review_analyses)
            metrics_counts = {}
            for item in product_db.review_analyses:
                for key, value in item.get("scores", {}).items():
                    if float(value) >= 5:
                        if key not in metrics_counts:
                            metrics_counts[key] = dict(count=0)
                        metrics_counts[key]["count"] += 1

            for key, value in metrics_counts.items():
                metrics_counts[key]["ratio"] = f'{round(metrics_counts[key]["count"] / total_reviews * 100)}%'
                metrics_counts[key]["total"] = total_reviews
        else:
            metrics_counts = {}

        result = APIAnalysisResult.model_validate(
            {"analyses": product_db.review_analyses, "summary": product_db.review_summary, "statistics": metrics_counts}
        )
        log.debug(result.statistics)
        return result


@router.post("/product/analyze_review_by_metrics")
async def review_analyze_by_metrics(
    params: ProductReviewAnalysisByMetricsIn,
):
    """
    根据用指定的指标分析评论
    """
    # 将指标转换为列表
    if isinstance(params.metrics, str):
        params.metrics = [params.metrics]

    pass


app.include_router(router, prefix="/api")

if __name__ == "__main__":
    run(app="api.main:app", reload=True, port=8199, host="0.0.0.0", workers=4)
    pass
