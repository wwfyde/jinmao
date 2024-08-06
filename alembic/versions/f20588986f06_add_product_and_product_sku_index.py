"""add product and product_sku index 

Revision ID: f20588986f06
Revises: d5ccb594979c
Create Date: 2024-08-01 15:05:24.329032

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f20588986f06'
down_revision: Union[str, None] = 'd5ccb594979c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index('ix_product_id', 'product', ['product_id'], unique=False)
    op.create_index('ix_review_count', 'product', ['review_count'], unique=False)
    op.create_index('ix_product_id', 'product_sku', ['product_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_product_id', table_name='product_sku')
    op.drop_index('ix_review_count', table_name='product')
    op.drop_index('ix_product_id', table_name='product')
    # ### end Alembic commands ###