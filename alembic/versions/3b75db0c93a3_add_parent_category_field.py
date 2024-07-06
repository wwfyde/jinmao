"""add parent_category field

Revision ID: 3b75db0c93a3
Revises: 4b57a52dfd24
Create Date: 2024-07-06 00:01:21.092707

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "3b75db0c93a3"
down_revision: Union[str, None] = "4b57a52dfd24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("product", sa.Column("parent_category", sa.String(length=256), nullable=True, comment="父商品类别"))
    op.add_column(
        "product", sa.Column("category_breadcrumbs", sa.String(length=1024), nullable=True, comment="商品类别级联")
    )
    op.drop_index("ix_image_url", table_name="product", mysql_prefix="FULLTEXT")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index("ix_image_url", "product", ["image_url"], unique=False, mysql_prefix="FULLTEXT")
    op.drop_column("product", "category_breadcrumbs")
    op.drop_column("product", "parent_category")
    # ### end Alembic commands ###
