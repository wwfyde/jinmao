from datetime import datetime
from typing import Literal

from sqlalchemy import String, Integer, DateTime, JSON, func, Boolean, BigInteger, Numeric, Text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (Index("ix_source_product_id", "source", "product_id", mysql_using="hash"), {"comment": "商品"})
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="内部ID")  # 内部ID
    product_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="源产品ID"
    )  # required: gap, jcpenney, target
    source: Mapped[Literal["gap", "target", "next", "jcpenney", "other"]] = mapped_column(
        String(64), default="other", nullable=True, comment="数据来源"
    )  # required: gap jcpenney, target
    product_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="商品名称"
    )  # required: gap, jcpenney, target
    sku_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="主款号 ID"
    )  # required: gap, jcpenney
    brand: Mapped[str | None] = mapped_column(String(64), comment="品牌")  # required: gap, jcpenney, target
    product_url: Mapped[str | None] = mapped_column(String(1024), comment="商品链接")  # required: gap, jcpenney, target
    image_url: Mapped[str | None] = mapped_column(
        String(1024), comment="商品主图链接"
    )  # required: gap, jcpenney, target
    image_url_outer: Mapped[str | None] = mapped_column(
        String(1024), comment="商品图片外链"
    )  # required: gap, jcpenney, target
    model_image_url: Mapped[str | None] = mapped_column(String(1024), comment="模特图片链接")
    model_image_urls: Mapped[list[str] | None] = mapped_column(JSON, comment="模特图片链接列表")
    rating: Mapped[float | None] = mapped_column(
        Numeric(2, 1), nullable=True, comment="评分"
    )  # required: gap, jcpenney, target
    review_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=0, comment="评论数"
    )  # required: gap, jcpenney, target
    rating_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=0, comment="评分数"
    )  # optional: target

    attributes: Mapped[dict | None] = mapped_column(
        JSON, comment="额外商品属性, 特点, 和描述bulletedCopyAttrs"
    )  # optional: jcpenney
    attributes_raw: Mapped[dict | list | None] = mapped_column(JSON, comment="原始属性")  # optional: gap专用
    category: Mapped[Literal["women", "men", "girls", "boys", "other"] | None] = mapped_column(
        String(256), comment="商品类别"
    )  # optional: jcpenney, target
    sub_category: Mapped[str | None] = mapped_column(String(256), comment="子类别")  # optional: jcpenney, target
    inner_category: Mapped[str | None] = mapped_column(String(256), comment="内部类别")  # optional: jcpenney, target
    gender: Mapped[Literal["F", "M", "O"]] = mapped_column(
        String(16), nullable=True, comment="性别, 根据类别推断"
    )  # required gap, jcpeney
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=func.now(), server_default=func.now(), nullable=True, index=True, comment="上新时间"
    )  # required: gap(none), jcpenney
    tags: Mapped[list[str] | None] = mapped_column(JSON, comment="标签")  # required
    review_summary: Mapped[str | None] = mapped_column(String(2048), comment="评论总结")

    style: Mapped[str | None] = mapped_column(String(64), comment="款式")  # deprecated 对应 商品名称name
    style_number: Mapped[str | None] = mapped_column(String(64), comment="款号")  # deprecated 对应product_id
    type: Mapped[str | None] = mapped_column(String(64), comment="类型")
    description: Mapped[str | None] = mapped_column(String(1024), comment="描述")
    remark: Mapped[str | None] = mapped_column(String(1024), comment="备注")

    store: Mapped[str | None] = mapped_column(String(64), comment="所属商店")

    source_id: Mapped[int | None] = mapped_column(BigInteger, comment="源商品ID")
    category_id: Mapped[int | None] = mapped_column(BigInteger, comment="类别ID")
    size: Mapped[str | None] = mapped_column(String(64), comment="尺码")
    material: Mapped[str | None] = mapped_column(String(128), comment="材质")
    fit: Mapped[str | None] = mapped_column(String(128), comment="适合")
    length: Mapped[str | None] = mapped_column(String(128), comment="服装长度")
    neckline: Mapped[str | None] = mapped_column(String(128), comment="领口")
    fabric_name: Mapped[str | None] = mapped_column(String(128), comment="面料名称")
    clothing_details: Mapped[str | None] = mapped_column(String(1024), comment="服装细节")
    package_quantity: Mapped[int | None] = mapped_column(Integer, comment="包装数量")
    care_instructions: Mapped[str | None] = mapped_column(String(1024), comment="护理和清洁")
    origin: Mapped[str | None] = mapped_column(String(128), comment="产地")
    raw_data: Mapped[dict | None] = mapped_column(JSON, comment="原始数据, json字段")
    is_deleted: Mapped[bool | None] = mapped_column(Boolean, default=False, comment="软删除")

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
    resource_url: Mapped[str | None] = mapped_column(String(1024), comment="外部资源链接")  # deprecated 同 商品url


class ProductSKU(Base):
    __tablename__ = "product_sku"
    __table_args__ = (
        Index("ix_source_sku_id", "source", "sku_id", mysql_using="hash"),
        Index("ix_source_product_id", "source", "product_id", mysql_using="hash"),
        {"comment": "商品SKU"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="内部ID")
    sku_id: Mapped[str | None] = mapped_column(String(128), comment="源SKU ID")  # required: gap, jcpenney, next, target
    source: Mapped[Literal["gap", "target", "next", "jcpenney", "other"]] = mapped_column(
        String(64), default="other", nullable=True, comment="数据来源"
    )  # required: gap, jcpenney, next, target
    product_id: Mapped[str | None] = mapped_column(
        String(128), comment="商品ID"
    )  # required: gap, jcpenney, next, target
    product_name: Mapped[str | None] = mapped_column(
        String(128), comment="商品名称"
    )  # required: gap, jcpenney, next, target
    gender: Mapped[Literal["F", "M", "O"]] = mapped_column(
        String(16), nullable=True, comment="性别, 根据类别推断, 主类别"
    )  # required gap, jcpeney
    sub_category: Mapped[Literal["women", "men", "girls", "boys", "other"] | None] = mapped_column(
        String(256), comment="商品类别"
    )  # optional: jcpenney, target
    inner_category: Mapped[str | None] = mapped_column(String(256), comment="内部类别")  # optional: jcpenney, target
    size: Mapped[str | None] = mapped_column(String(64), comment="尺码")  # required: gap, jcpenney, next, target
    color: Mapped[str | None] = mapped_column(String(64), comment="颜色")  # required: gap, jcpenney, next, target
    material: Mapped[str | None] = mapped_column(String(128), comment="材质")
    source_id: Mapped[int | None] = mapped_column(BigInteger, comment="源商品ID")
    sku_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="SKU名称")
    description: Mapped[str | None] = mapped_column(String(1024), comment="商品描述")
    attributes: Mapped[dict | None] = mapped_column(
        JSON, comment="额外商品属性, 特点, 和描述bulletedCopyAttrs"
    )  # optional: jcpenney, next
    attributes_raw: Mapped[dict | list | None] = mapped_column(JSON, comment="原始属性")  # optional: gap专用
    product_url: Mapped[str | None] = mapped_column(String(1024), comment="商品链接")  # optional: jcpenney, next
    category_id: Mapped[int | None] = mapped_column(BigInteger, comment="类别ID")
    image_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="商品图片"
    )  # optional: next, target
    image_url_outer: Mapped[str | None] = mapped_column(
        String(1024), comment="商品图片外链"
    )  # required: gap, jcpenney, target
    model_image_url: Mapped[str | None] = mapped_column(String(1024), comment="模特图片链接")
    model_image_urls: Mapped[list[str] | None] = mapped_column(JSON, comment="模特图片链接列表")
    style: Mapped[str | None] = mapped_column(String(128), comment="服装风格")
    inventory: Mapped[int | None] = mapped_column(Integer, comment="库存")
    inventory_status: Mapped[str | None] = mapped_column(String(32), comment="库存状态")
    vendor: Mapped[str | None] = mapped_column(String(64), comment="供应商")
    fit: Mapped[str | None] = mapped_column(String(128), comment="适合人群")
    origin: Mapped[str | None] = mapped_column(String(128), comment="产地")  # optional: next

    # 其他数据
    length: Mapped[str | None] = mapped_column(String(128), comment="服装长度")
    neckline: Mapped[str | None] = mapped_column(String(128), comment="领口")
    fabric_name: Mapped[str | None] = mapped_column(String(128), comment="面料名称")
    clothing_details: Mapped[str | None] = mapped_column(String(1024), comment="服装细节")
    package_quantity: Mapped[int | None] = mapped_column(Integer, comment="包装数量")
    care_instructions: Mapped[str | None] = mapped_column(String(1024), comment="护理和清洁")
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


class ProductReview(Base):
    __tablename__ = "product_review"
    __table_args__ = (
        Index("ix_source_product_id", "source", "product_id", mysql_using="hash"),
        {"comment": "商品评论"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    review_id: Mapped[str | None] = mapped_column(String(64), comment="源评论ID")  # required: gap, jcpenney, next
    source: Mapped[Literal["gap", "target", "next", "jcpenney", "other"]] = mapped_column(
        String(64), default="other", nullable=True, comment="数据来源"
    )  # required: gap, jcpenney, next
    product_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="商品ID"
    )  # required: gap, jcpenney, next
    product_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="商品标题"
    )  # optional: gap, next
    sku_id: Mapped[str | None] = mapped_column(String(64), comment="SKU ID")  # optional: gap, next
    rating: Mapped[float | None] = mapped_column(
        Numeric(2, 1), comment="评分"
    )  # CheckConstraint('rating >= 1 AND rating <= 5'  # required: gap, jcpenney, next
    title: Mapped[str | None] = mapped_column(String(1024), comment="评论标题")  # required: gap, jcpenney, next
    comment: Mapped[str | None] = mapped_column(Text, comment="评论内容")  # required: gap, jcpenney, next
    photos: Mapped[list[str] | None] = mapped_column(JSON, comment="评论图片")  # optional: target
    photos_outer: Mapped[list[str] | None] = mapped_column(JSON, comment="评论外部数据源")  # optional: target
    nickname: Mapped[str | None] = mapped_column(String(64), comment="昵称")  # required: gap, jcpenney, next
    helpful_votes: Mapped[int | None] = mapped_column(Integer, default=0, comment="按顶票数")  # required: gap, jcpenney
    not_helpful_votes: Mapped[int | None] = mapped_column(Integer, comment="按踩票数")  # required: gap, jcpenney
    # 评论分析字段
    # quality: Mapped[float | None] = mapped_column(
    #     Numeric(3, 1), comment="质量"
    # )  # required: gap, jcpenney, next, target
    analysis: Mapped[dict | None] = mapped_column(JSON, comment="评论分析")  # required: gap, jcpenney, next, target
    metrics: Mapped[dict | list | None] = mapped_column(
        JSON, comment="评论指标"
    )  # required: gap, jcpenney, next, target
    token_usage: Mapped[dict | list | None] = mapped_column(
        JSON, comment="LLM token 消耗"
    )  # required: gap, jcpenney, next, target
    helpful_score: Mapped[float | None] = mapped_column(Numeric(6, 1), comment="有用评分")  # optional: gap
    is_deleted: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True, comment="软删除")
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
    __table_args__ = {"comment": "商品图片"}
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


class ProductProcessedStatus(Base):
    __tablename__ = "task_status"
    __table_args__ = {"comment": "任务状态"}
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="商品ID")
    source: Mapped[Literal["gap", "target", "next", "jcpenney", "other"]] = mapped_column(
        String(64), default="other", comment="数据来源"
    )
    task_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="任务ID")
    status: Mapped[Literal["pending", "running", "finished", "failed"]] = mapped_column(
        String(64), nullable=False, comment="任务状态"
    )
    message: Mapped[str | None] = mapped_column(String(1024), comment="消息")
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
    is_deleted: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True, comment="软删除")
