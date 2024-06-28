from typing import cast

from fastapi import FastAPI, Depends, APIRouter
from sqlalchemy import select, ColumnElement
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from uvicorn import run

from api.doubao import analyze_reviews, summarize_reviews
from api.schemas import (
    ProductReviewIn,
    ProductReviewAnalysis,
    ProductReviewAnalysisByMetricsIn,
)
from . import log
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
    # log.info("访问根目录")
    return RedirectResponse(url="/docs")


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

    log.info(f"分析商品评论[{len(reviews)}]")

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
    # if isinstance(params.extra_metrics, list):
    #     params.extra_metrics = ", ".join(params.extra_metrics)
    if not product_db.review_analyses or params.from_api is True:
        if params.llm == "ark":
            result = await analyze_reviews(review_dicts)
        else:
            result = await analyze_reviews(review_dicts)
        # 将分析结果保存到数据库

        # stmt = (
        #     update(Product)
        #     .where(Product.product_id == params.product_id, Product.source == params.source)  # noqa
        #     .values(review_summary=summary, is_review_analyzed=True)
        # )
        # db.execute(stmt)
        product_db.is_review_analyzed = True
        product_db.review_analyses = result
        db.commit()  # 显式提交事务

        # 获取评论统计数据
        metrics_counts = metrics_statistics(result, threshold=params.threshold) if result else {}
        # return {"analyses": result, "statistics": metrics_counts}
        return {"analyses": metrics_counts}
    else:
        # metrics_stmt = select(ProductReview.metrics).where(
        #     cast(ColumnElement, ProductReview.product_id == params.product_id),
        #     cast(ColumnElement, ProductReview.source == params.source),
        # )
        # metrics = db.execute(metrics_stmt).scalar().all()
        metrics_counts = (
            metrics_statistics(product_db.review_analyses, threshold=params.threshold)
            if product_db.review_analyses
            else {}
        )

        # return {"analyses": product_db.review_analyses, "statistics": metrics_counts}
        return {"analyses": metrics_counts}


def metrics_statistics(reviews: list[dict], threshold: float | int | None = None) -> dict:
    total_reviews = len(reviews)
    metrics_counts = {}
    for item in reviews:
        # log.info(f"{item=}")
        for key, value in item.get("scores", {}).items():
            score = float(value.get("score", 0))
            cn = value.get("cn", key)
            en = value.get("en", key)
            if float(value.get("score")) >= threshold or 5.0:
                if key not in metrics_counts:
                    metrics_counts[key] = dict(count=0, total_score=0, cn=cn, en=en)

                metrics_counts[key]["count"] += 1
                metrics_counts[key]["total_score"] += score

    for key, value in metrics_counts.items():
        count = metrics_counts[key]["count"]
        metrics_counts[key]["ratio"] = f"{round(count / total_reviews * 100)}%"
        metrics_counts[key]["total"] = total_reviews
        if count > 0:
            metrics_counts[key]["average_score"] = round(metrics_counts[key]["total_score"] / count, 2)
        else:
            metrics_counts[key]["average_score"] = 0.0
    return metrics_counts


@router.post(
    "/product/review_summary",
    summary="商品评论总结",
)
async def review_summary(params: ProductReviewIn, db: Session = Depends(get_db)):
    """
    评论总结
    """

    stmt = select(ProductReview).where(
        cast(ColumnElement, ProductReview.product_id == params.product_id),
        cast(ColumnElement, ProductReview.source == params.source),
    )
    # 从数据库中获取商品下的所有评论
    reviews = db.execute(stmt).scalars().all()

    log.info(f"总结商品{params.product_id=}, {params.source=}评论[{len(reviews)}]")

    # 将 ORM对象转换为字典
    review_dicts = [ProductReviewAnalysis.model_validate(review).model_dump(exclude_unset=True) for review in reviews]
    # log.debug(review_dicts)

    # 查询商品信息 并检查总结是否存在
    stmt = select(Product).where(
        cast(ColumnElement, Product.product_id == params.product_id),
        cast(ColumnElement, Product.source == params.source),
    )
    product_db = db.execute(stmt).scalars().one_or_none()

    if not product_db.review_summary or params.from_api is True:
        if params.llm == "ark":
            result = await summarize_reviews(review_dicts)
        else:
            result = await summarize_reviews(review_dicts)

        product_db.review_analyses = result
        db.commit()  # 显式提交事务

        # 获取空间数据
        return {"summary": result}
    else:
        # metrics_stmt = select(ProductReview.metrics).where(
        #     cast(ColumnElement, ProductReview.product_id == params.product_id),
        #     cast(ColumnElement, ProductReview.source == params.source),
        # )
        # metrics = db.execute(metrics_stmt).scalar().all()

        return {"summary": product_db.review_summary}


@router.post("/product/analyze_review_by_metrics", summary="额外指标分析")
async def review_analysis_by_metrics(
    params: ProductReviewAnalysisByMetricsIn,
    db: Session = Depends(get_db),
):
    """
    根据用指定的指标分析评论
    """
    # 将指标转换为列表
    if isinstance(params.extra_metrics, str):
        params.extra_metrics = [params.extra_metrics]
    pass
    stmt = select(ProductReview).where(
        cast(ColumnElement, ProductReview.product_id == params.product_id),
        cast(ColumnElement, ProductReview.source == params.source),
    )
    reviews = db.execute(stmt).scalars().all()

    log.info(f"按指标分析商品评论[{len(reviews)}]")

    # 将 ORM对象转换为字典
    review_dicts = [ProductReviewAnalysis.model_validate(review).model_dump(exclude_unset=True) for review in reviews]
    log.debug(review_dicts)

    # 查询商品信息
    stmt = select(Product).where(
        cast(ColumnElement, Product.product_id == params.product_id),
        cast(ColumnElement, Product.source == params.source),
    )
    product_db = db.execute(stmt).scalars().one_or_none()

    # 获取原有指标
    # last_metrics = product_db.extra_metrics
    # 通过redis 设置商品分析结果缓存, 超过7天自动重新分析
    extra_metrics_str = ", ".join(params.extra_metrics)
    if not product_db.review_analyses or params.from_api is True:
        if params.llm == "ark":
            result = await analyze_reviews(review_dicts, extra_metrics=extra_metrics_str)
        else:
            result = await analyze_reviews(review_dicts, extra_metrics=extra_metrics_str)
        # 将分析结果保存到数据库

        # product_db.review_analyses_extra = product_db.review_analyses_extra + result
        # db.commit()  # 显式提交事务

        # 获取评论统计数据
        metrics_counts = metrics_statistics(result, threshold=params.threshold) if result else {}
        return {"analyses": result, "statistics": metrics_counts}
    else:
        # metrics_stmt = select(ProductReview.metrics).where(
        #     cast(ColumnElement, ProductReview.product_id == params.product_id),
        #     cast(ColumnElement, ProductReview.source == params.source),
        # )
        # metrics = db.execute(metrics_stmt).scalar().all()
        metrics_counts = (
            metrics_statistics(product_db.review_analyses, threshold=params.threshold)
            if product_db.review_analyses
            else {}
        )

        return {"analyses": product_db.review_analyses, "statistics": metrics_counts}


app.include_router(router, prefix="/api")

if __name__ == "__main__":
    run(app="api.main:app", reload=True, port=8199, host="0.0.0.0", workers=4)
    pass
