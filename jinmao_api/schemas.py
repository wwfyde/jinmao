from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict, field_serializer, model_validator


class ReviewMetric(BaseModel):
    en: str | None = Field(None, description="英文名")
    cn: str | None = Field(None, description="中文名")
    score: float | None = Field(0, description="分数")


class ReviewAnalysisMetrics(BaseModel):
    quality: ReviewMetric = Field(None, description="质量")
    warmth: ReviewMetric = Field(None, description="保暖性")
    comfort: ReviewMetric = Field(None, description="舒适度")
    softness: ReviewMetric = Field(None, description="柔软性")
    preference: ReviewMetric = Field(None, description="偏好")
    repurchase_intent: ReviewMetric = Field(None, description="回购意向")
    appearance: ReviewMetric = Field(None, description="外观")
    fit: ReviewMetric = Field(None, description="合身度")

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
    product_id: str | None = None
    id: str | None = None
    # comment: str
    source: str | None = None
    lang: Literal["zh", "en"] = Field("en", description="语言")

    from_api: bool | None = Field(False, description="是否从api分析")  # 是否走API
    llm: Literal["ark", "claude", "azure", "bedrock", "openai"] | None = Field("ark", description="LLM模型")
    extra_metrics: list[str] | str | None = Field(None, description="需要分析的指标")
    threshold: float | None = Field(5.0, description="指标阈值")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": "728681",
                "source": "gap",
                "lang": "en",
                "from_api": False,
                "llm": "ark",
                "extra_metrics": ["cost-effectiveness", "实用性"],
            }
        },
        title="评论分析输入验证",
    )

    @model_validator(mode="after")
    def check_fields_after(self):
        if self.product_id and self.source:
            print("Product ID and Source are provided.")
        if self.id:
            print("ID is provided.")

        # if not ((self.review_id and self.source) or self.id):
        if not (self.product_id and self.source) and not self.id:
            raise ValueError("请传入id ,或review_id和source.")

        return self


class ProductReviewIn(BaseModel):
    product_id: str = Field(..., description="商品ID")
    source: str = Field(..., description="来源")
    lang: Literal["zh", "en"] = Field("en", description="语言")
    llm: Literal["ark", "claude", "azure", "bedrock", "openai"] | None = Field("ark", description="LLM模型")
    from_api: bool | None = Field(False, description="是否从api分析")  # 是否走API
    # extra_metrics: list[str] | str | None = Field(False, description="额外分析指标")
    threshold: float | None = Field(5.0, description="指标阈值")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": "728681",
                "source": "gap",
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
    created_at_inner: datetime | None = None
    updated_at_inner: datetime | None = None

    @field_serializer("id", when_used="always")
    def transform_id_to_str(id: int) -> str:
        return str(id)


class ProductReviewSchema(ProductReviewModel):
    id: int | str | None = None


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


if __name__ == "__main__":
    metrics = ReviewAnalysisMetrics(c="9.9", quality="7.2").model_dump()
    print(metrics)
