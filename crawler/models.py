from datetime import datetime
from typing import Literal

from sqlalchemy import String, Integer, DateTime, JSON, func, Boolean, BigInteger, Numeric
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "product"
    __table_args__ = {"comment": "商品"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str | None] = mapped_column(String(128), nullable=False, comment="商品标题")
    brand: Mapped[str | None] = mapped_column(String(64), comment="品牌")
    style: Mapped[str | None] = mapped_column(String(64), comment="款式")
    style_number: Mapped[str | None] = mapped_column(String(64), comment="款号")
    type: Mapped[str | None] = mapped_column(String(64), comment="类型")
    image_url: Mapped[str | None] = mapped_column(String(1024), comment="图片链接")
    tags: Mapped[list[str] | None] = mapped_column(JSON, comment="标签")
    description: Mapped[str | None] = mapped_column(String(1024), comment="描述")
    remark: Mapped[str | None] = mapped_column(String(1024), comment="备注")
    gender: Mapped[Literal["F", "M", "O"]] = mapped_column(String(2), nullable=True, comment="性别")
    review_score: Mapped[float | None] = mapped_column(Numeric(2, 1), nullable=True, comment="评分")
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0, comment="评论数")

    store: Mapped[str | None] = mapped_column(String(64), comment="所属商店")
    is_deleted: Mapped[bool | None] = mapped_column(Boolean, default=False, comment="软删除")
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=func.now(), server_default=func.now(), nullable=True, comment="上新时间"
    )
    tenant_id: Mapped[int | None] = mapped_column(BigInteger, comment="租户ID")
    tenant_name: Mapped[str | None] = mapped_column(String(64), comment="租户名称")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=func.now(),
        server_default=func.now(),
        nullable=True,
        comment="创建时间",
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        server_default=func.now(),
        server_onupdate=func.now(),
        nullable=True,
        comment="更新时间",
    )

    # 资源标记
    source: Mapped[Literal["gap", "target", "next", "jcpenney", "other"]] = mapped_column(
        String(64), default="other", nullable=True, comment="数据来源"
    )
    resource_url: Mapped[str | None] = mapped_column(String(1024), comment="外部资源链接")


class ProductDetail(Base):
    """ " deprecated"""

    __tablename__ = "product_detail"
    __table_args__ = {"comment": "商品详情"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="ID")
    source_id: Mapped[int | None] = mapped_column(BigInteger, comment="源商品ID")
    name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="商品名称")
    category_id: Mapped[int | None] = mapped_column(BigInteger, comment="类别ID")
    category: Mapped[str | None] = mapped_column(BigInteger, comment="商品类别")
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="商品图片")
    description: Mapped[str | None] = mapped_column(String(1024), comment="商品描述")
    size: Mapped[str | None] = mapped_column(String(64), comment="尺码")
    material: Mapped[str | None] = mapped_column(String(128), comment="材质")
    style: Mapped[str | None] = mapped_column(String(128), comment="服装风格")
    fit: Mapped[str | None] = mapped_column(String(128), comment="适合")
    length: Mapped[str | None] = mapped_column(String(128), comment="服装长度")
    neckline: Mapped[str | None] = mapped_column(String(128), comment="领口")
    fabric_name: Mapped[str | None] = mapped_column(String(128), comment="面料名称")
    clothing_details: Mapped[str | None] = mapped_column(String(1024), comment="服装细节")
    package_quantity: Mapped[int | None] = mapped_column(Integer, comment="包装数量")
    care_instructions: Mapped[str | None] = mapped_column(String(1024), comment="护理和清洁")
    origin: Mapped[str | None] = mapped_column(String(128), comment="产地")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="软删除")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=func.now(),
        server_default=func.now(),
        nullable=True,
        comment="创建时间",
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        server_default=func.now(),
        server_onupdate=func.now(),
        nullable=True,
        comment="更新时间",
    )
    source: Mapped[Literal["gap", "target", "next", "jcpenney", "other"]] = mapped_column(
        String(64), default="other", comment="数据来源"
    )
    raw_data: Mapped[dict | None] = mapped_column(JSON, comment="原始数据")
    resource_url: Mapped[str] = mapped_column(String(1024), comment="外部资源链接")


class ProductSKU(Base):
    __tablename__ = "product_sku"
    __table_args__ = {"comment": "商品SKU"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, comment="商品ID")
    product_name: Mapped[str] = mapped_column(String(64), comment="商品名称")
    size: Mapped[str | None] = mapped_column(String(64), comment="尺码")
    color: Mapped[str | None] = mapped_column(String(64), comment="颜色")
    material: Mapped[str | None] = mapped_column(String(128), comment="材质")
    source_id: Mapped[int | None] = mapped_column(BigInteger, comment="源商品ID")
    name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="商品名称")
    description: Mapped[str | None] = mapped_column(String(1024), comment="商品描述")
    category_id: Mapped[int] = mapped_column(BigInteger, comment="类别ID")
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="商品图片")
    style: Mapped[str | None] = mapped_column(String(128), comment="服装风格")
    inventory: Mapped[int | None] = mapped_column(Integer, comment="库存")
    inventory_status: Mapped[str | None] = mapped_column(String(32), comment="库存状态")
    vendor: Mapped[str | None] = mapped_column(String(64), comment="供应商")
    fit: Mapped[str | None] = mapped_column(String(128), comment="适合人群")

    # 其他数据
    length: Mapped[str | None] = mapped_column(String(128), comment="服装长度")
    neckline: Mapped[str | None] = mapped_column(String(128), comment="领口")
    fabric_name: Mapped[str | None] = mapped_column(String(128), comment="面料名称")
    clothing_details: Mapped[str | None] = mapped_column(String(1024), comment="服装细节")
    package_quantity: Mapped[int | None] = mapped_column(Integer, comment="包装数量")
    care_instructions: Mapped[str | None] = mapped_column(String(1024), comment="护理和清洁")
    origin: Mapped[str | None] = mapped_column(String(128), comment="产地")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="软删除")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=func.now(),
        server_default=func.now(),
        nullable=True,
        comment="创建时间",
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        server_default=func.now(),
        server_onupdate=func.now(),
        nullable=True,
        comment="更新时间",
    )


class ProductImage(Base):
    __tablename__ = "product_image"
    __table_agrs__ = {"comment": "商品图片"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=True, comment="所属商品")
    sku_id: Mapped[int | None] = mapped_column(BigInteger, comment="SKU ID")
    image_source_url: Mapped[str] = mapped_column(String(1024), comment="图片链接")
    type: Mapped[Literal["main", "detail", "other"]] = mapped_column(String(64), comment="图片类型")

    is_deleted: Mapped[bool | None] = mapped_column(Boolean, default=False, comment="软删除")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=func.now(),
        server_default=func.now(),
        nullable=True,
        comment="创建时间",
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        server_default=func.now(),
        server_onupdate=func.now(),
        nullable=True,
        comment="更新时间",
    )


class Category(Base):
    __tablename__ = "category"
    __table_args__ = {"comment": "类别"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="类别名称")
    source: Mapped[Literal["gap", "target", "next", "jcpenney", "other"]] = mapped_column(
        String(64), default="other", comment="数据来源"
    )
    parent_id: Mapped[int | None] = mapped_column(Integer, comment="父类别ID")


class ProductReview(Base):
    __tablename__ = "product_review"
    __table_args__ = {"comment": "商品评论"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, comment="商品ID")
    product_name: Mapped[str | None] = mapped_column(String(128), nullable=False, comment="商品标题")

    sku_id: Mapped[int | None] = mapped_column(BigInteger, comment="SKU ID")
    rating: Mapped[float | None] = mapped_column(
        Numeric(2, 1), comment="评分等级"
    )  # CheckConstraint('rating >= 1 AND rating <= 5'
    title: Mapped[str | None] = mapped_column(String(128), comment="评论标题")
    comment: Mapped[str | None] = mapped_column(String(1024), comment="评论详情")
    is_deleted: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True, comment="软删除")
    nickname: Mapped[str | None] = mapped_column(String(64), comment="昵称")
    source: Mapped[Literal["gap", "target", "next", "jcpenney", "other"]] = mapped_column(
        String(64), default="other", nullable=True, comment="数据来源"
    )
    helpful_votes: Mapped[int | None] = mapped_column(Integer, default=0, comment="按赞票数")
    not_helpful_votes: Mapped[int | None] = mapped_column(Integer, comment="按踩票数")
    helpful_score: Mapped[float | None] = mapped_column(Numeric(2, 1), comment="有用评分")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=func.now(),
        server_default=func.now(),
        nullable=True,
        comment="创建时间",
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        server_default=func.now(),
        server_onupdate=func.now(),
        nullable=True,
        comment="更新时间",
    )
