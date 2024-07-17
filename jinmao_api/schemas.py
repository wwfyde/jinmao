from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict, field_serializer, model_validator


class ReviewMetric(BaseModel):
    en: str | None = Field(None, description="英文名")
    cn: str | None = Field(None, description="中文名")
    score: float | None = Field(0, description="分数")


class ReviewAnalysisMetrics(BaseModel):
    quality: ReviewMetric | str | int | float = Field(None, description="质量")
    warmth: ReviewMetric | str | int | float = Field(None, description="保暖性")
    comfort: ReviewMetric | str | int | float = Field(None, description="舒适度")
    softness: ReviewMetric | str | int | float = Field(None, description="柔软性")
    preference: ReviewMetric | str | int | float = Field(None, description="偏好")
    repurchase_intent: ReviewMetric | str | int | float = Field(None, description="回购意向")
    appearance: ReviewMetric | str | int | float = Field(None, description="外观")
    fit: ReviewMetric | str | int | float = Field(None, description="合身度")

    # __pydantic_extra__: dict  # 对额外字段添加约束
    model_config = ConfigDict(
        extra="allow",
        # coerce_numbers_to_str=True,  # 允许将数组转换成字符串
    )


class APIAnalysisResult(BaseModel):
    summary: str | None = None
    analyses: list[dict] | None = Field(None, description="分析结构")
    statistics: list | dict | str | None = None


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


class ProductAttribute(BaseModel):
    neckline: str | None = Field(None, description="领口")
    origin: str | None = Field(None, description="产地")
    material: str | None = Field(None, description="材质")
    fabric: str | None = Field(None, description="面料")
    sleeve: str | None = Field(None, description="袖子")
    size: list[str] | str | None = Field(None, description="尺寸")
    color: list[str] | str | None = Field(None, description="颜射")

    # __pydantic_extra__: dict  # 对额外字段添加约束

    model_config = ConfigDict(extra="allow", coerce_numbers_to_str=True)

    pass


class ProductReviewAnalysisByMetricsIn(BaseModel):
    product_id: str
    # comment: str
    source: str
    lang: Literal["zh", "en"] = Field("en", description="语言")
    date_start: datetime | None = Field(None, description="时间范围起始")
    date_end: datetime | None = Field(None, description="时间范围截止")
    from_api: bool | None = Field(False, description="是否从api分析")  # 是否走API
    llm: Literal["ark", "claude", "azure", "bedrock", "openai"] | None = Field("ark", description="LLM模型")
    extra_metrics: list[str] | str = Field(..., description="需要分析的指标")
    threshold: float | None = Field(5.0, description="指标阈值")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": "728681",
                "source": "gap",
                "date_start": "2024-07-09",
                "date_end": "2024-07-10",
                "lang": "en",
                "from_api": False,
                "llm": "ark",
                "extra_metrics": ["cost-effectiveness", "实用性"],
            }
        },
        title="评论分析输入验证",
    )

    # @model_validator(mode="after")
    # def check_fields_after(self):
    #     if self.product_id and self.source:
    #         print("Product ID and Source are provided.")
    #     if self.id:
    #         print("ID is provided.")
    #
    #     # if not ((self.review_id and self.source) or self.id):
    #     if not (self.product_id and self.source) and not self.id:
    #         raise ValueError("请传入id ,或review_id和source.")
    #
    #     return self


class ProductReviewIn(BaseModel):
    product_id: str = Field(..., description="商品ID")
    source: str = Field(..., description="来源")
    lang: Literal["zh", "en"] = Field("en", description="语言")
    llm: Literal["ark", "claude", "azure", "bedrock", "openai"] | None = Field("ark", description="LLM模型")
    from_api: bool | None = Field(False, description="是否从api分析")  # 是否走API
    # extra_metrics: list[str] | str | None = Field(False, description="额外分析指标")
    date_start: datetime | None = Field(None, description="时间范围起始")
    date_end: datetime | None = Field(None, description="时间范围截止")
    threshold: float | None = Field(5.0, description="指标阈值")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": "728681",
                "source": "gap",
                "date_start": "2024-07-09",
                "date_end": "2024-07-10",
                "lang": "en",
                "from_api": False,
                "llm": "ark",
            }
        },
        title="评论分析输入验证",
    )


class ProductReviewModel(
    BaseModel,
):
    model_config = ConfigDict(from_attributes=True)

    id: int
    review_id: str
    product_id: str
    source: str
    sku_id: str | None = None
    rating: float | None = None
    title: str | None = None
    comment: str | None = None
    photos: list[str] | None = None
    outer_photos: list[str] | None = None
    nickname: str | None = None
    helpful_votes: int | None = None
    not_helpful_votes: int | None = None
    is_deleted: bool | None = None
    gathered_at: datetime | None = None
    last_gathered_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_serializer("id", when_used="always")
    def transform_id_to_str(id: int) -> str:
        return str(id)


class ProductReviewSchema(ProductReviewModel):
    id: int | str | None = None


class ProductReviewTranslationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    review_id: str
    product_id: str
    source: str
    rating: float | None = None
    title: str | None = None
    comment: str | None = None


class ProductTranslationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    source: str
    product_name: str | None = None
    description: str | None = None
    attributes: ProductAttribute | None = None
    gender: str | None = None


class ProductSKUTranslationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    sku_id: str
    source: str
    sku_name: str | None = None
    size: str | None = None
    color: str | None = None
    material: str | None = None


class ProductExtraMetric(BaseModel):
    product_id: str = Field(..., description="商品id")
    source: str = Field(..., description="数据源")

    extra_metrics: list[str] | str = Field(..., description="额外指标指标")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": "728681",
                "source": "gap",
                "metric": ["实用性", "cost-effectiveness"],
            }
        }
    )


class ReviewFilter(BaseModel):
    product_id: str = Field(..., description="商品id")
    source: str = Field(..., description="数据源")
    page: int = 1
    page_size: int = 10
    include_deleted: str | None = Field(None, description="软删除选项")
    sort_by: Literal["created_at", "id"] = Field("created_at", description="排序")
    sort_order: Literal["desc", "asc"] = Field("desc", description="正反序")
    metric: Literal[
        "quality", "warmth", "comfort", "softness", "preference", "repurchase_intent", "appearance", "fit"
    ] = Field(..., description="过滤指标名称")
    threshold: float | None = Field(5.0, description="指标阈值")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": "728681",
                "source": "gap",
                "metric": "quality",
                "page": 1,
                "page_size": 10,
                "sort_by": "created_at",
                "sort_order": "desc",
                "threshold": 5.0,
            }
        },
    )


class ProductReviewAnalysisValidator(
    BaseModel,
):
    model_config = ConfigDict(from_attributes=True)

    review_id: str
    product_id: str
    source: str
    rating: float | None = None
    title: str | None = None
    comment: str | None = None
    nickname: str | None = None
    helpful_votes: int | None = None
    not_helpful_votes: int | None = None


if __name__ == "__main__":
    metrics = ReviewAnalysisMetrics(c="9.9", quality="7.2").model_dump()
    print(metrics)
