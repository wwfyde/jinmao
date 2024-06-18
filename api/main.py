from datetime import datetime
from typing import Literal

from fastapi import FastAPI, Depends, APIRouter
from pydantic import BaseModel, model_validator, ConfigDict, field_serializer
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

from api import log
from api.doubao import analyze_dobao
from crawler.db import get_db
from crawler.models import ProductReview

app = FastAPI()
# 设置允许跨域访问
app.add_middleware(
    CORSMiddleware,
    # allow_origins=origins,
    allow_origins=["molook.cn", "uat.molook.cn:543"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
router = APIRouter()


class ReviewIn(BaseModel):
    review_id: str | None = None
    id: str | None = None
    # comment: str
    source: str | None = None

    @model_validator(mode="after")
    def check_fields_after(self):
        if self.review_id and self.source:
            print("Review ID and Source are provided.")
        if self.id:
            print("ID is provided.")

        # if not ((self.review_id and self.source) or self.id):
        if not (self.review_id and self.source) and not self.id:
            raise ValueError("请传入id ,或review_id和source.")

        return self


class ProductReviewIn(BaseModel):
    product_id: str
    source: str
    lang: Literal["zh", "en"] = "en"
    from_api: bool | None = False  # 是否走API


class ProductReviewModel(
    BaseModel,
):
    model_config = ConfigDict(from_attributes=True)

    id: int
    review_id: str
    product_id: str
    source: str
    product_name: str | None = None
    sku_id: str | None = None
    rating: float | None = None
    title: str | None = None
    comment: str | None = None
    nickname: str | None = None
    helpful_votes: int | None = None
    not_helpful_votes: int | None = None
    helpful_score: int | None = None
    is_deleted: bool | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_serializer("id", when_used="always")
    def transform_id_to_str(id: int) -> str:
        return str(id)


class ProductReviewAnalysis(
    BaseModel,
):
    model_config = ConfigDict(from_attributes=True)

    review_id: str
    product_id: str
    source: str
    product_name: str | None = None
    rating: float | None = None
    title: str | None = None
    comment: str | None = None
    nickname: str | None = None
    helpful_votes: int | None = None
    not_helpful_votes: int | None = None
    helpful_score: int | None = None


@app.get("/")
async def root():
    log.info("访问根目录")
    return RedirectResponse(url="/docs")


@router.post("/review/analysis/haiku", summary="分析")
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


@router.post("/product/review_analysis/doubao", summary="商品评论分析")
async def review_analysis_with_doubao(review: ProductReviewIn, db: Session = Depends(get_db)):
    stmt = select(ProductReview).where(
        ProductReview.product_id == review.product_id, ProductReview.source == review.source
    )
    reviews = db.execute(stmt).scalars().all()

    log.info(f"分析商品评论[{len(reviews)}]: {reviews}")
    review_dicts = [ProductReviewAnalysis.model_validate(review).model_dump(exclude_unset=True) for review in reviews]
    print(review_dicts)
    result = analyze_dobao(review_dicts)
    return result


app.include_router(router, prefix="/api")

if __name__ == "__main__":
    # run(app="api.main:app", reload=True, port=8199, workers=4)
    pass
