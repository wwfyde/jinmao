from pydantic import BaseModel, Field


class ReviewAnalysisMetrics(BaseModel):
    quality: float | None = None
    warmth: float | None = None
    comfort: float | None = None
    softness: float | None = None
    likability: float | None = None
    repurchase_intent: float | None = None
    positive_sentiment: float | None = None
    input_tokens: float | None = None
    output_tokens: float | None = None
    processing_time: float | None = None


class APIAnalysisResult(BaseModel):
    summary: str
    analyses: list[dict] = Field(..., description="分析结构")
    # statistics: list | None = None
