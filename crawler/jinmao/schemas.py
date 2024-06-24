from pydantic import BaseModel, Field, ConfigDict


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


if __name__ == "__main__":
    pa = ProductAttribute(a=12, fabric=12)
    print(pa.model_dump(exclude_unset=True))
    print(pa.__pydantic_extra__)
