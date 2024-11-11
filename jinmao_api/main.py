import logging
from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from redis import Redis
from sqlalchemy import and_, asc, delete, desc, distinct, func, insert, or_, select, text, tuple_, update
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from uvicorn import run

from crawler.db import get_db
from crawler.deps import get_redis_cache_sync
from crawler.models import Product, ProductDetail, ProductReview, ProductReviewAnalysis, ProductSKU, \
    ReviewAnalysisExtraMetric
from jinmao_api import log
from jinmao_api.doubao import analyze_reviews, summarize_reviews
from jinmao_api.schemas import (ProductReviewAnalysisByMetricsIn, ProductReviewAnalysisValidator, ProductReviewIn,
                                ReviewFilter)

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
                    reviews[:1000]]
    # log.debug(review_dicts)
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
            zh = value.get("zh", key)
            en = value.get("en", key)
            if float(value.get("score")) >= (threshold or 5.0):
                if key not in metrics_counts:
                    metrics_counts[key] = dict(count=0, total_score=0, zh=zh, en=en)

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
            affected_rows = db.execute(update_stmt).rowcount
            log.debug(f"更新{affected_rows}条记录")
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
                    reviews[:1000]]
    # log.debug(review_dicts)

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
        metrics_counts = extra_metrics_statistics(new_results, threshold=params.threshold) if results else {}
        # 将分析结果保存到数据库
        if not params.date_start and not params.date_end:
            with db.begin_nested():
                for result in new_results:
                    db.execute(
                        update(ProductReviewAnalysis)
                        .where(
                            ProductReviewAnalysis.review_id == result.get("review_id"),
                            ProductReviewAnalysis.source == params.source
                        )  # 根据评论的唯一标识符更新
                        .values(extra_metrics=result.get("scores"), version_id=params.version_id)
                    )
                    for name, value in result.get("scores").items():
                        # 查询是否存在, 不存在则插入
                        stmt = select(ReviewAnalysisExtraMetric).where(
                            ReviewAnalysisExtraMetric.review_id == result.get("review_id"),
                            ReviewAnalysisExtraMetric.source == params.source,
                            ReviewAnalysisExtraMetric.version_id == params.version_id,
                            ReviewAnalysisExtraMetric.name == name,
                        )
                        metric_name_result = db.execute(stmt).scalars().one_or_none()
                        if metric_name_result:
                            # update
                            db.execute(
                                update(ReviewAnalysisExtraMetric).where(stmt.whereclause).values(
                                    value=value,

                                )
                            )
                            log.debug("更新额外指标成功")

                        else:
                            # insert
                            stmt = insert(ReviewAnalysisExtraMetric).values(
                                review_id=result.get("review_id"),
                                product_id=params.product_id,
                                source=params.source,
                                version_id=params.version_id,
                                name=name,
                                value=value,
                            )
                            db.execute(stmt)
                            log.debug("插入额外指标成功")

            log.info("插入索引指标的ProductReview成功")

            # 将额外指标分析结果保存到数据库
            update_stmt = (
                update(Product)
                .where(Product.product_id == params.product_id, Product.source == params.source)
                .values(
                    extra_review_statistics=metrics_counts,
                    extra_review_analyses=new_results,
                    extra_metrics=params.extra_metrics,
                    current_version=params.version_id,
                )
            )
            affected_rows = db.execute(update_stmt).rowcount
            db.commit()
            log.debug(f"更新{affected_rows}条记录")

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

    # 删除所有额外指标
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
        affected_rows = db.execute(update_stmt).rowcount

        # 删除额外指标
        delete_stmt = delete(ReviewAnalysisExtraMetric).where(
            ReviewAnalysisExtraMetric.product_id == params.product_id,
            ReviewAnalysisExtraMetric.source == params.source,
            ReviewAnalysisExtraMetric.version_id == params.version_id,

        )
        db.execute(delete_stmt)
        log.debug(f"更新{affected_rows}条记录")
        db.commit()
        log.info("删除所有额外指标成功")
        return {"analyses": None, "statistics": None}
    else:
        log.info("不分删除")

    # 部分指标删除 逻辑优化, 仅删除指定的指标

    # 获取已有指标
    product_db: Product = db.execute(select(Product).where(Product.product_id == params.product_id,
                                                           Product.source == params.source)).scalars().one()
    last_metrics = product_db.extra_metrics
    log.debug(f"上次指标: {last_metrics}")
    # 需要删除的指标
    to_delete_metrics = list(set(last_metrics) - set(params.extra_metrics))
    if not to_delete_metrics:
        log.info("没有需要删除的指标")
        return {"analyses": None, "statistics": product_db.extra_review_statistics}
    log.debug(f"待删除指标: {to_delete_metrics}")
    delete_stmt = delete(ReviewAnalysisExtraMetric).where(
        ReviewAnalysisExtraMetric.product_id == params.product_id,
        ReviewAnalysisExtraMetric.source == params.source,
        ReviewAnalysisExtraMetric.version_id == params.version_id,
        ReviewAnalysisExtraMetric.name.in_(to_delete_metrics),
    )
    db.execute(delete_stmt)

    # 操作product数据库
    # 过滤
    last_extra_review_statistics: dict = product_db.extra_review_statistics
    last_extra_review_analyses: list = product_db.extra_review_analyses
    new_extra_review_analyses = []
    for metric in to_delete_metrics:
        last_extra_review_statistics.pop(metric, None)
        for analysis in last_extra_review_analyses:
            analysis.get("scores", {}).pop(metric, None)
            new_extra_review_analyses.append(analysis)

    update_stmt = (
        update(Product)
        .where(Product.product_id == params.product_id, Product.source == params.source)
        .values(
            extra_review_statistics=last_extra_review_statistics,
            extra_review_analyses=new_extra_review_analyses,
            extra_metrics=params.extra_metrics,
            current_version=params.version_id,
        )
    )
    affected_rows = db.execute(update_stmt).rowcount
    db.commit()
    log.debug(f"更新{affected_rows}条记录")
    return {"analyses": None, "statistics": last_extra_review_statistics}


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


class PageSize(int, Enum):
    small = 20
    medium = 50
    large = 100

class Source(str, Enum):
    next = "next"
    gap = "gap"
    target = "target"
    jcpenney = "jcpenney"


class Gender(str, Enum):
    women = 'women'
    men = 'men'
    girls = 'girls'
    boys = 'boys'
    unisex = 'unisex'
    unknown = 'unknown'


class SearchProductParams(BaseModel):
    keyword: str | None = Field(None, description="搜索关键词")
    source: Source | None = Field(None, description="数据源")
    brands: list[str] = Field(None, description="品牌列表")
    categories: list[str] | None = Field(None, description="类别列表")
    genders: list[str] | None = Field(None, description="性别列表", examples=["women", "men"])
    tags: list[str] | None = Field(None, description="标签列表")
    product_id: str | None = Field(None, description="商品ID或SKU ID", validation_alias=AliasChoices("product_id","productId"))
    language_code: str | None = Field(default="en", description="语言代码", validation_alias=AliasChoices("language_code", "languageCode"))
    use_index: bool = Field(False, description="是否使用索引", validation_alias=AliasChoices("use_index", "useIndex"))

    product_name: str | None = Field(None, description="商品名称", validation_alias=AliasChoices("product_name", "productName"))
    page_current: int = Field(1, ge=1, description="当前页", validation_alias=AliasChoices("page_current", "pageCurrent"))
    page_size: PageSize = Field(20, ge=1, le=100, examples=[20, 50, 100], validation_alias=AliasChoices("page_size", "pageSize"))
    # refresh: bool = False  # TODO 是否刷新 索引
    # TODO 支持多排序
    sort_by: Literal['review_count', 'gathered_at', 'id'] | None = Field('review_count', description="排序字段", validation_alias=AliasChoices("sort_by", "sortBy"))
    sort_order: Literal["desc", "asc"] | None = Field("desc", description="排序方式", validation_alias=AliasChoices("sort_order", "sortOrder"))
    released_at_start: str | None = Field(None, description="发布时间开始", validation_alias=AliasChoices("released_at_start", "releasedAtStart"))
    released_at_end: str | None = Field(None, description="发布时间结束", validation_alias=AliasChoices("released_at_end", "releasedAtEnd"))

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "keyword": "pyjamas",
                "page": 1,
                "page_size": 20,
                "refresh": False,
            }
        },
        use_enum_values=True,
    )


class ProductOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        protected_namespaces=(), 
    )
    source: Source = Field(..., description="数据源", alias="source")
    id: str | int = Field(..., description="商品ID", alias="id")
    product_id: str = Field(..., description="商品ID", alias="productId", validation_alias=AliasChoices("product_id", "productId"))
    primary_sku_id: str | None = Field(None, description="主SKU ID", alias="primarySkuId", validation_alias=AliasChoices("primary_sku_id", "primarySkuId"))
    brand: str | None = Field(None, description="品牌", alias="brand")
    product_url: str | None = Field(None, description="商品链接", alias="productUrl", validation_alias=AliasChoices("product_url", "productUrl"))
    rating: float | None = Field(None, description="评分", alias="rating")
    review_count: int | None = Field(None, description="评论数", alias="reviewCount", validation_alias=AliasChoices("review_count", "reviewCount"))
    rating_count: int | None = Field(None, description="评分数", alias="ratingCount", validation_alias=AliasChoices("rating_count", "ratingCount"))

    # attributes: dict | list | None = Field(None, description="属性", alias="attributes")
    description: str | None = Field(None, description="描述", alias="description")
    # attributes_raw: dict | list | None = Field(None, description="原始属性", alias="attributesRaw", validation_alias=AliasChoices("attributes_raw", "attributesRaw"))
    category: str | None = Field(None, description="类别", alias="category")
    gender: Gender | None = Field(None, description="性别", alias="gender")
    released_at: str | datetime | None = Field(None, description="发布时间", alias="releasedAt", validation_alias=AliasChoices("released_at", "releasedAt"))
    tags: list[str] | None = Field(None, description="标签", alias="tags")
    is_review_analyzed: bool | None = Field(None, description="是否已分析评论", alias="isReviewAnalyzed", validation_alias=AliasChoices("is_review_analyzed", "isReviewAnalyzed"))
    # review_analyses: list[dict] | None = Field(None, description="评论分析", alias="reviewAnalyses", validation_alias=AliasChoices("review_analyses", "reviewAnalyses"))
    # extra_metrics: list[str] | None = Field(None, description="额外指标", alias="extraMetrics", validation_alias=AliasChoices("extra_metrics", "extraMetrics"))
    # extra_review_analyses: list[dict] | None = Field(None, description="额外评论分析", alias="extraReviewAnalyses", validation_alias=AliasChoices("extra_review_analyses", "extraReviewAnalyses"))
    # review_statistics: dict | None = Field(None, description="评论统计", alias="reviewStatistics", validation_alias=AliasChoices("review_statistics", "reviewStatistics"))
    # extra_review_statistics: dict | None = Field(None, description="额外评论统计", alias="extraReviewStatistics", validation_alias=AliasChoices("extra_review_statistics", "extraReviewStatistics"))
    # review_summary: dict | None = Field(None, description="评论总结", alias="reviewSummary", validation_alias=AliasChoices("review_summary", "reviewSummary"))
    # remark: str | None = Field(None, description="备注", alias="remark")
    category_id: str | None = Field(None, description="类别ID", alias="categoryId", validation_alias=AliasChoices("category_id", "categoryId"))
    is_deleted: bool | None = Field(None, description="是否已删除", alias="isDeleted", validation_alias=AliasChoices("is_deleted", "isDeleted"))
    gathered_at: str | datetime| None = Field(None, description="采集时间", alias="gatheredAt", validation_alias=AliasChoices("gathered_at", "gatheredAt"))
    last_gathered_at: str | datetime| None = Field(None, description="最后采集时间", alias="lastGatheredAt", validation_alias=AliasChoices("last_gathered_at", "lastGatheredAt"))
    created_at: str | datetime | None = Field(None, description="创建时间", alias="createdAt", validation_alias=AliasChoices("created_at", "createdAt"))
    updated_at: str | datetime | None = Field(None, description="更新时间", alias="updatedAt", validation_alias=AliasChoices("updated_at", "updatedAt"))
    current_version: str | None = Field(None, description="当前版本", alias="currentVersion", validation_alias=AliasChoices("current_version", "currentVersion"))
    image: str | None = Field(None, description="图片", alias="image")

    #sku_id:从ProductSKU中获取
    sku_id: str | None = Field(None, description="SKU ID", alias="skuId", validation_alias=AliasChoices("sku_id", "skuId"))
    model_image_urls: list[str] | None = Field(None, description="模型图片链接", alias="modelImageUrls", validation_alias=AliasChoices("model_image_urls", "modelImageUrls"))
    outer_model_image_urls: list[str] | None = Field(None, description="外部模型图片链接", alias="outerModelImageUrls", validation_alias=AliasChoices("outer_model_image_urls", "outerModelImageUrls"))
    image_url: str | None = Field(None, description="图片链接", alias="imageUrl", validation_alias=AliasChoices("image_url", "imageUrl"))
    outer_image_url: str | None = Field(None, description="外部图片链接", alias="outerImageUrl", validation_alias=AliasChoices("outer_image_url", "outerImageUrl"))
    color: str | None = Field(None, description="颜色", alias="color")
    size: str | None = Field(None, description="尺寸", alias="size")
    material: str | None = Field(None, description="材质", alias="material")
    sku_name: str | None = Field(None, description="SKU名称", alias="skuName", validation_alias=AliasChoices("sku_name", "skuName"))

    main_category: str | None = Field(None, description="主类别", alias="mainCategory")
    sub_category: str | None = Field(None, description="子类别", alias="subCategory")


@router.post("/product/search", summary="商品搜索")
async def search_product(
        params: Annotated[SearchProductParams, Query(description="搜索参数")],
        db: Session = Depends(get_db),
        cache: Redis = Depends(get_redis_cache_sync)
):
    """
    相关度排序搜索
    """
    print(params)

    # #使用联表查询
    # p = aliased(Product)
    # sku = aliased(ProductSKU)
    stmt = select(Product, ProductSKU, ProductDetail).join(ProductSKU, and_(Product.product_id == ProductSKU.product_id, Product.source == ProductSKU.source)).join(ProductDetail, and_(ProductSKU.product_id == ProductDetail.product_id, ProductSKU.source == ProductDetail.source))

    # 不使用联表查询
    # stmt = select(Product).where(Product.is_deleted == False)

            # .join(ProductDetail, and_(ProductSKU.product_id==ProductDetail.product_id, ProductSKU.source==ProductDetail.source)))
    if params.use_index and params.source == "next":
        # 从Redis中获取商品ID
        product_ids = cache.lrange(f"jinmao:{params.source}:{params.keyword}", 0, -1)
    if params.source:
        stmt = stmt.where(Product.source == params.source)
    # if any(params.keyword in keyword for keyword in {'pyjamas', 'pajamas'}):
    if params.tags:
        tag_conditions = [
            func.json_contains(Product.tags, func.json_quote(tag)) == 1
            for tag in params.tags
        ]
        stmt = stmt.where(or_(*tag_conditions))
    if params.brands:
        stmt = stmt.where(Product.brand.in_(params.brands))
    if params.categories:
        stmt = stmt.where(Product.category.in_(params.categories))
    if params.keyword and params.source == "next":
        if 'pyjamas' in params.keyword.lower() or 'pajamas' in params.keyword.lower() or '睡衣' in params.keyword:
            keyword = "pyjamas"
            stmt = stmt.where(or_(Product.category.ilike("%pyjamas%"), Product.category.ilike("%pajamas%"), Product.product_name.ilike("%pyjamas%"), Product.product_name.ilike("%pajamas%")))
            start = params.page_size * (params.page_current - 1)
            end = start + params.page_size

            products = cache.lrange(f"jinmao:{params.source}:{params.keyword}:indb", start, end)
            formatted_products = []
            for product in products:
                product_id, sku_id = product.split(", ")
                formatted_products.append((product_id, sku_id))
            print(formatted_products)
            stmt = stmt.where(
                    tuple_(Product.product_id, ProductSKU.sku_id).in_(formatted_products)
                )
            results = db.execute(stmt)
            total = cache.llen(f"jinmao:{params.source}:{keyword}:indb")
            sku_total = total
            serial_results = []
            for result in results:
                product: Product = result.Product
                product_sku: ProductSKU = result.ProductSKU
                product_detail: ProductDetail = result.ProductDetail
                product_dict = ProductOut.model_validate(product)
                product_dict.sku_id = product_sku.sku_id
                product_dict.model_image_urls = product_sku.model_image_urls or product_sku.outer_model_image_urls
                product_dict.outer_model_image_urls = product_sku.outer_model_image_urls
                product_dict.image_url = product_sku.image_url or product_sku.outer_image_url
                product_dict.outer_image_url = product_sku.outer_image_url
                product_dict.image = product_sku.image_url or product_sku.outer_image_url
                product_dict.main_category = product_detail.main_category
                product_dict.sub_category = product_detail.sub_category
                serial_results.append(product_dict)

            # log.warning(f"{total=}, {sku_total=}, {len(serial_results)=}, {serial_results=}")
            return {
                "code": "00000",
                "data": {
                    "total": total,
                    "SKUTotal": sku_total,
                    "pageCurrent": params.page_current,
                    "pageSize": params.page_size,
                    "data": serial_results
                },
                "msg": "一切ok"
            }

            return {

            }
    if params.genders:
        stmt = stmt.where(Product.gender.in_(params.genders))

        ...
    if params.product_id:
        stmt = stmt.where(
            or_(
                Product.product_id.ilike(f"%{params.product_id.strip()}%"),
                ProductSKU.sku_id.ilike(f"%{params.product_id.strip()}%")
            )
        )
    if params.product_name:
        stmt = stmt.where(Product.product_name.ilike(f"%{params.product_name.strip()}%"))
    if params.released_at_start:
        stmt = stmt.where(Product.released_at >= params.released_at_start)
    if params.released_at_end:
        stmt = stmt.where(Product.released_at <= params.released_at_end)
    if params.sort_by:
        log.debug(f"{params.sort_by}, {params.sort_order}")
        order = desc(params.sort_by) if params.sort_order == "desc" else asc(params.sort_by)
        stmt = stmt.order_by(order)
    stmt = stmt.limit(params.page_size).offset((params.page_current - 1) * params.page_size)
    log.debug(stmt.compile())
    log.debug(stmt)
    results = db.execute(stmt)
    if stmt.whereclause is not None:
        print(stmt.whereclause)
        sku_total = db.execute(select(func.count("*")).select_from(Product).join(ProductSKU, and_(Product.product_id == ProductSKU.product_id, Product.source == ProductSKU.source)).where(stmt.whereclause)).scalar()
        total = db.execute(select(func.count(distinct(Product.product_id))).select_from(Product).join(ProductSKU, and_(Product.product_id == ProductSKU.product_id, Product.source == ProductSKU.source)).where(stmt.whereclause)).scalar()
    else:
        sku_total = db.execute(select(func.count("*")).select_from(Product).join(ProductSKU, and_(Product.product_id == ProductSKU.product_id, Product.source == ProductSKU.source))).scalar()
        total = db.execute(select(func.count("*")).select_from(Product)).scalar()

    total_pages = (total + params.page_size - 1) // params.page_size

    # for result in results:
    #     product_sku: ProductSKU = result.ProductSKU
    #     product: Product = result.Product
    #     result = ProductOut.model_validate(product)
    #     result.sku_id = product_sku.sku_id
    #     result.model_image_urls = product_sku.model_image_urls
    #
    #     # serial_results.append(result)
    #     serial_results.append(product.id)
    # for result in results:
    #     serial_results.append((result.id, result.gathered_at, result.review_count))
    # return serial_results
    serial_results = []
    for result in results:
        product: Product = result.Product
        product_sku: ProductSKU = result.ProductSKU
        product_detail: ProductDetail = result.ProductDetail
        product_dict = ProductOut.model_validate(product)
        product_dict.sku_id = product_sku.sku_id
        product_dict.model_image_urls = product_sku.model_image_urls or product_sku.outer_model_image_urls
        product_dict.outer_model_image_urls = product_sku.outer_model_image_urls
        product_dict.image_url = product_sku.image_url or product_sku.outer_image_url
        product_dict.outer_image_url = product_sku.outer_image_url
        product_dict.image = product_sku.image_url or product_sku.outer_image_url
        product_dict.main_category = product_detail.main_category
        product_dict.sub_category = product_detail.sub_category
        serial_results.append(product_dict)

    # log.warning(f"{total=}, {sku_total=}, {len(serial_results)=}, {serial_results=}")
    return {
        "code": "00000",
        "data": {
            "total": total,
            "SKUTotal": sku_total,
            "pageCurrent": params.page_current,
            "pageSize": params.page_size,

            "data": serial_results
        },
        "msg": "一切ok"
    }
    if params.refresh:
        if any(keyword in params.keyword for keyword in {'pyjamas', 'pajamas'}):
            # stmt = select(Product).where(
            #     Product.name.ilike("%pyjamas%")
            # )
            # db.execute(stmt)
            keyword = "pyjamas"
            source = "next"
            all_products_sorted = cache.lrange(f"jinmao:{source}:{keyword}", 0, -1)
            for product in all_products_sorted:
                print(f"{product}, {type(product)=}")
                product_id, sku_id = product.decode().split(", ")
                stmt = select(ProductSKU).where(
                    ProductSKU.product_id == product_id,
                    ProductSKU.sku_id == sku_id,
                    source == "next"
                )
                product_sku = db.execute(stmt).scalars().one_or_none()
                if product_sku:
                    r = cache.lpush(f"jinmao:{source}:{keyword}:indb", product)

            indb_products = cache.lrange(f"jinmao:{source}:{keyword}:indb", 0, -1)
            return {
                "redis_result": all_products_sorted,
                "indb_result": indb_products,
                "indb_count": len(indb_products),
                "all_count": len(all_products_sorted)
            }

            return {
                "redis_result": all_products_sorted
            }
            ...
    else:
        if any(keyword in params.keyword for keyword in {'pyjamas', 'pajamas'}):
            keyword = "pyjamas"
            source = "next"
            start = (params.page - 1) * params.page_size
            end = start + params.page_size - 1
            products: list[bytes] = cache.lrange(f"jinmao:{source}:{keyword}:indb", start, end)
            product_index = [tuple(product.decode().split(', ')) for product in products]
            stmt = select(ProductSKU).where(
                tuple_(ProductSKU.product_id, ProductSKU.sku_id).in_(product_index),
                ProductSKU.source == source
            )
            sku_list = db.execute(stmt).scalars().all()
            return {
                "total": cache.llen(f"jinmao:{source}:{keyword}:indb"),
                "redis_result": product_index,
                "sku_list": sku_list
            }


        return False
        ...

    


app.include_router(router, prefix="/api")

if __name__ == "__main__":
    run(app="api.main:app", reload=True, port=8199, host="0.0.0.0", workers=4)
    pass
