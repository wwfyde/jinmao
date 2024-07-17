import logging

from fastapi import FastAPI, Depends, APIRouter
from sqlalchemy import select, update, and_, func, desc, text, asc, insert
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from uvicorn import run

from jinmao_api.doubao import analyze_reviews, summarize_reviews
from jinmao_api.schemas import (
    ProductReviewIn,
    ProductReviewAnalysisValidator,
    ProductReviewAnalysisByMetricsIn,
    ReviewFilter,
)
from jinmao_api import log
from crawler.db import get_db
from crawler.models import ProductReview, Product, ProductReviewAnalysis, ReviewAnalysisExtraMetric

log.setLevel(logging.DEBUG)

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
        ProductReview.product_id == params.product_id,
        ProductReview.source == params.source,
    )
    log.debug(f"{params.date_start=}, {params.date_end}")
    if params.date_start:
        stmt = stmt.where(ProductReview.created_at >= params.date_start)
    if params.date_end:
        stmt = stmt.where(ProductReview.created_at <= params.date_end)
    log.debug(f"{params.date_start=}, {params.date_end=}")
    reviews = db.execute(stmt).scalars().all()

    log.info(f"分析商品评论[{len(reviews)}]")

    # 将 ORM对象转换为字典
    review_dicts = [ProductReviewAnalysisValidator.model_validate(review).model_dump(exclude_unset=True) for review in
                    reviews]
    log.debug(review_dicts)
    if not reviews:
        return {"analyses": None, "statistics": None}

    # 查询商品信息
    stmt = select(Product).where(
        Product.product_id == params.product_id,
        Product.source == params.source,
    )
    product_db = db.execute(stmt).scalars().one_or_none()
    # 通过redis 设置商品分析结果缓存, 超过7天自动重新分析
    # if isinstance(params.extra_metrics, list):
    #     params.extra_metrics = ", ".join(params.extra_metrics)
    if params.date_start or params.date_end:
        params.from_api = True
    if not product_db.review_analyses or params.from_api is True:
        if params.llm == "ark":
            results = await analyze_reviews(review_dicts)
        else:
            results = await analyze_reviews(review_dicts)

        # 分析指标统计
        metrics_counts = metrics_statistics(results, threshold=params.threshold) if results else {}

        # 将分析结果保存到数据库
        if not params.date_start and not params.date_end:
            try:
                for result in results:
                    review_id = result.get("review_id")
                    scores: dict = result.get("scores")

                    db.execute(
                        insert(ProductReviewAnalysis)
                        .values(
                            review_id=review_id,
                            product_id=params.product_id,
                            source=params.source,
                            quality=scores.get("quality", {}).get("score"),
                            warmth=scores.get("warmth", {}).get("score"),
                            comfort=scores.get("comfort", {}).get("score"),
                            softness=scores.get("softness", {}).get("score"),
                            preference=scores.get("preference", {}).get("score"),
                            repurchase_intent=scores.get("repurchase_intent", {}).get("score"),
                            appearance=scores.get("appearance", {}).get("score"),
                            fit=scores.get("fit", {}).get("score"),
                        )
                    )
                db.commit()
            except Exception as exc:
                log.error(f"插入评论指标失败{exc}")
                db.rollback()

            # 将统计和单一分析结果写入数据库

            update_stmt = (
                update(Product)
                .where(Product.product_id == params.product_id, Product.source == params.source)
                .values(
                    review_statistics=metrics_counts,
                    is_review_analyzed=True,
                    review_analyses=results,
                )
            )
            affected_rows = db.execute(update_stmt).rowcount
            log.debug(f"更新{affected_rows}条记录")
            db.commit()
        else:
            log.info("当前使用了日期过滤, 将不会保存结果")
            # 获取评论统计数据
        # product_db_new = db.execute(stmt).scalars().first()
        # product_db_new.review_statistics = metrics_counts
        # product_db_new.is_review_analyzed = True
        # product_db_new.review_analyses = results
        # db.add(product_db_new)
        # db.commit()
        return {"analyses": None, "statistics": metrics_counts}
        # return {"analyses": metrics_counts}
    else:
        metrics_counts = product_db.review_statistics

        return {"analyses": None, "statistics": metrics_counts}
        # return {"analyses": metrics_counts}


def metrics_statistics(reviews: list[dict], threshold: float | int | None = None) -> dict:
    total_reviews = len(reviews)
    metrics_counts = {}
    for item in reviews:
        # log.info(f"{item=}")
        for key, value in item.get("scores", {}).items():
            score = float(value.get("score", 0))
            cn = value.get("cn", key)
            en = value.get("en", key)
            if float(value.get("score")) >= (threshold or 5.0):
                if key not in metrics_counts:
                    metrics_counts[key] = dict(count=0, total_score=0, cn=cn, en=en)

                metrics_counts[key]["count"] += 1
                metrics_counts[key]["total_score"] += score

    for key, value in metrics_counts.items():
        count = metrics_counts[key].get("count", 0)
        metrics_counts[key]["ratio"] = f"{round(count / total_reviews * 100)}%"
        metrics_counts[key]["total"] = total_reviews
        if count > 0:
            metrics_counts[key]["average_score"] = round(metrics_counts[key]["total_score"] / count, 2)
        else:
            metrics_counts[key]["average_score"] = 0.0
    return metrics_counts


def extra_metrics_statistics(reviews: list[dict], threshold: float | int | None = None) -> dict:
    total_reviews = len(reviews)
    metrics_counts = {}
    for item in reviews:
        # log.info(f"{item=}")
        for key, value in item.get("scores", {}).items():
            if value and float(value) >= (threshold or 5.0):
                if key not in metrics_counts:
                    metrics_counts[key] = dict(count=0, total_score=0)

                metrics_counts[key]["count"] += 1
                metrics_counts[key]["total_score"] += float(value)

    for key, value in metrics_counts.items():
        count = metrics_counts[key].get("count", 0)
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
        ProductReview.product_id == params.product_id, ProductReview.source == params.source
    )
    if params.date_start:
        stmt = stmt.where(ProductReview.created_at >= params.date_start)
    if params.date_end:
        stmt = stmt.where(ProductReview.created_at <= params.date_end)
    log.debug(f"{params.date_start=}, {params.date_end=}")
    # 从数据库中获取商品下的所有评论
    reviews = db.execute(stmt).scalars().all()

    log.info(f"总结商品{params.product_id=}, {params.source=}评论[{len(reviews)}]")

    # 将 ORM对象转换为字典
    review_dicts = [ProductReviewAnalysisValidator.model_validate(review).model_dump(exclude_unset=True) for review in
                    reviews]
    # log.debug(review_dicts)
    if not reviews:
        return {"summary": None}

    # 查询商品信息 并检查总结是否存在
    stmt = select(Product).where(Product.product_id == params.product_id, Product.source == params.source)
    product_db = db.execute(stmt).scalars().one_or_none()
    if params.date_start or params.date_end:
        params.from_api = True

    if not product_db.review_summary or params.from_api is True:
        if params.llm == "ark":
            result = await summarize_reviews(review_dicts)
        else:
            result = await summarize_reviews(review_dicts)
        if not params.date_start and not params.date_end:

            update_stmt = (
                update(Product)
                .where(Product.product_id == params.product_id, Product.source == params.source)
                .values(
                    review_summary=result,
                )
            )
            affected_rows = db.execute(update_stmt)
            db.commit()
            # product_db.review_summary = result
            # db.add(product_db)
            # db.commit()  # 显式提交事务
        else:
            log.info("当前使用了日期过滤, 将不会保存结果")

        # 获取空间数据
        return {"summary": result}
    else:
        return {"summary": product_db.review_summary}


@router.post("/product/analyze_review_by_metrics", summary="额外指标分析")
async def review_analysis_with_extra_metrics(
        params: ProductReviewAnalysisByMetricsIn,
        db: Session = Depends(get_db),
):
    """
    根据用指定的指标分析评论
    """
    return await analyze_review_by_metrics(params, db)


async def analyze_review_by_metrics(
        params: ProductReviewAnalysisByMetricsIn,
        db: Session,
):
    # 将指标转换为列表
    if isinstance(params.extra_metrics, str):
        params.extra_metrics = [params.extra_metrics]

    # 将指标键名风格替换为下划线
    params.extra_metrics = [metric.replace("-", "_").replace(" ", "_").lower() for metric in params.extra_metrics]
    stmt = select(ProductReview).where(
        ProductReview.product_id == params.product_id, ProductReview.source == params.source
    )
    if params.date_start:
        stmt = stmt.where(ProductReview.created_at >= params.date_start)
    if params.date_end:
        stmt = stmt.where(ProductReview.created_at <= params.date_end)
    reviews = db.execute(stmt).scalars().all()

    log.info(f"按指标分析商品评论, 共[{len(reviews)}]条")

    # 将 ORM对象转换为字典
    review_dicts = [ProductReviewAnalysisValidator.model_validate(review).model_dump(exclude_unset=True) for review in
                    reviews]
    log.debug(review_dicts)

    if not reviews:
        return {"analyses": None, "statistics": None}
    # 查询商品信息
    stmt = select(Product).where(Product.product_id == params.product_id, Product.source == params.source)
    product_db = db.execute(stmt).scalars().one_or_none()

    # 获取原有指标
    if params.date_start or params.date_end:
        params.from_api = True

    last_metrics = product_db.extra_metrics
    # 如果前端传入的
    if last_metrics and (set(last_metrics) != set(params.extra_metrics)):
        params.from_api = True
    # 通过redis 设置商品分析结果缓存, 超过7天自动重新分析
    if not product_db.extra_review_statistics or params.from_api is True:
        log.debug("通过接口分析")
        if params.llm == "ark":
            results = await analyze_reviews(review_dicts, extra_metrics=params.extra_metrics)
        else:
            results = await analyze_reviews(review_dicts, extra_metrics=params.extra_metrics)
        log.debug(results)
        # 提示词过滤, 仅保留params.extra_extra_metrics中的数据, 去除额外的字段
        new_results = []
        for result in results:
            new_result = result
            new_result["scores"] = {extra_metric: result.get("scores", {}).get(extra_metric) for extra_metric in
                                    params.extra_metrics}
            new_results.append(new_result)

        log.debug(new_results)

        # 获取评论统计数据
        metrics_counts = extra_metrics_statistics(results, threshold=params.threshold) if results else {}
        # 将分析结果保存到数据库
        if not params.date_start and not params.date_end:
            try:
                for result in new_results:
                    db.execute(
                        update(ProductReviewAnalysis)
                        .where(
                            ProductReviewAnalysis.review_id == result.get("review_id"),
                            ProductReviewAnalysis.source == params.source
                        )  # 根据评论的唯一标识符更新
                        .values(extra_metrics=result.get("scores"))
                    )
                    db.commit()
                    extra_metrics_to_insert = []
                    for name, value in result.get("scores").items():
                        extra_metrics_to_insert.append(
                            ReviewAnalysisExtraMetric(
                                review_id=result.get("review_id"),
                                product_id=params.product_id,
                                source=params.source,
                                name=name,
                                value=value,

                            )
                        )
                    # stmt = insert(ReviewAnalysisExtraMetric).values(
                    #     review_id=result.get("review_id"),
                    #     product_id=params.product_id,
                    #     source=params.source,
                    #     name='name',
                    #     value='value',
                    # )
                    db.add_all(extra_metrics_to_insert)
                    db.commit()
            except Exception as exc:
                db.rollback()
                log.error(f"插入额外指标失败{exc}, 撤销")
            log.info("插入索引指标的ProductReview成功")

            update_stmt = (
                update(Product)
                .where(Product.product_id == params.product_id, Product.source == params.source)
                .values(
                    extra_review_statistics=metrics_counts,
                    extra_review_analyses=results,
                    extra_metrics=params.extra_metrics,
                )
            )
            affected_rows = db.execute(update_stmt)
            db.commit()
            # product_db_new = db.execute(stmt).scalars().first()
            # product_db_new.extra_review_statistics = metrics_counts
            # product_db_new.extra_review_analyses = results
            # product_db_new.extra_metrics = params.extra_metrics
            # db.add(product_db_new)
            # db.commit()
        else:
            log.info("当前使用了日期过滤, 将不会保存结果")
        log.info(f"接口执行完毕{metrics_counts}")
        return {"analyses": None, "statistics": metrics_counts}
    else:
        log.debug("查数据库")
        # return {"analyses": product_db.review_analyses, "statistics": product_db.extra_review_statistics}
        return {"analyses": None, "statistics": product_db.extra_review_statistics}


@router.post("/product/extra_metrics", summary="额外指标查询")
async def extra_metrics(params: ProductReviewIn, db: Session = Depends(get_db)):
    """
    从数据库获取
    """
    extra_metrics_db: Product | None = (
        db.execute(select(Product).where(Product.product_id == params.product_id, Product.source == params.source))
        .scalars()
        .one_or_none()
    )
    if extra_metrics_db:
        return {
            "extra_metrics": extra_metrics_db.extra_metrics,
            "extra_statistics": extra_metrics_db.extra_review_statistics,
        }
    else:
        return {
            "extra_metrics": None,
            "extra_statistics": None,
        }


@router.patch("/product/extra_metrics", summary="删除额外指标")
async def update_extra_metrics(params: ProductReviewAnalysisByMetricsIn, db: Session = Depends(get_db)):
    """
    从数据库获取
    """
    # stmt = (
    #     update(Product)
    #     .where(Product.product_id == params.product_id, Product.source == params.source)
    #     .values(extra_metrics=params.extra_metrics)
    # )
    #
    # affected_rows = db.execute(stmt)
    # db.commit()
    # 更新指标后更新数据库
    # if isinstance(params.extra_metrics, str):
    #     params.extra_metrics = [params.extra_metrics]
    log.info(f"用户传入的指标: {params.extra_metrics}")
    params.extra_metrics = [metric.replace("-", "_").replace(" ", "_").lower() for metric in params.extra_metrics]

    if not params.extra_metrics:
        update_stmt = (
            update(Product)
            .where(Product.product_id == params.product_id, Product.source == params.source)
            .values(
                extra_review_statistics=None,
                extra_review_analyses=None,
                extra_metrics=None,
            )
        )
        affected_rows = db.execute(update_stmt)
        db.commit()
        log.info("所有额外指标成功")
        return True
    else:
        log.info("指标没变化")

    # 总是走API重新分析一遍
    params.from_api = True
    try:
        return await analyze_review_by_metrics(params, db)
    except Exception as exc:
        log.error(f"更新额外指标失败{exc}")


@router.post("/product/review/metrics_filter", summary="评论指标过滤")
async def review_metrics_filter(params: ReviewFilter, db: Session = Depends(get_db)):
    metric_field = getattr(ProductReviewAnalysis, params.metric)
    log.debug(metric_field)
    stmt = select(ProductReviewAnalysis).where(
        and_(
            ProductReviewAnalysis.product_id == params.product_id,
            ProductReviewAnalysis.source == params.source,
            metric_field >= params.threshold,
        )
    )
    # if not params.include_deleted:
    #     stmt = stmt.where(ProductReview.is_deleted == "0")  # noqa
    if params.sort_by:
        order = desc(text(params.sort_by)) if params.sort_order == "desc" else asc(params.sort_by)
        stmt = stmt.order_by(order)

    total_count = db.execute(
        select(func.count(ProductReviewAnalysis.id)).select_from(ProductReviewAnalysis).where(stmt.whereclause)
    ).scalar()
    total_pages = (total_count + params.page_size - 1) // params.page_size
    stmt = stmt.limit(params.page_size).offset((params.page - 1) * params.page_size)
    # log.debug(stmt.compile())

    try:
        log.debug(stmt.compile())
        items = db.execute(stmt).scalars().all()
        return {
            "items": items,
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": params.page,
            "page_size": params.page_size,
            "page_count": len(items),
        }
    except Exception as exc:
        log.error(f"请检查传入指标是否正确: {exc}")
        raise ValueError(f"请传入正确的指标, {exc}")

    pass


app.include_router(router, prefix="/api")

if __name__ == "__main__":
    run(app="api.main:app", reload=True, port=8199, host="0.0.0.0", workers=4)
    pass
