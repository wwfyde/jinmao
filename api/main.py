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
async def haiku_analysis(review: ReviewIn, db: Session = Depends(get_db)):
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
async def review_analysis_with_doubao(params: ProductReviewIn, db: Session = Depends(get_db)):
    """
    1. 优先从数据库查询, 如果没有则调用doubao分析;
    2. 当

    """
    stmt = select(ProductReview).where(
        ProductReview.product_id == params.product_id,  # noqa
        ProductReview.source == params.source,  # noqa
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
    if not product_db.is_review_analyzed or params.from_api is True:
        if params.llm == "ark":
            result = await analyze_doubao(review_dicts)
        else:
            result = await analyze_doubao(review_dicts)
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

        return result
    else:
        # metrics_stmt = select(ProductReview.metrics).where(
        #     cast(ColumnElement, ProductReview.product_id == params.product_id),
        #     cast(ColumnElement, ProductReview.source == params.source),
        # )
        # metrics = db.execute(metrics_stmt).scalar().all()

        return {"analyses": product_db.review_analyses, "summary": product_db.review_summary, "statistics": ""}


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
