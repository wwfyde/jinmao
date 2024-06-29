"""add extra_review_analyses field on product table

Revision ID: fea1dd86bb9c
Revises: 3d99fc41bf58
Create Date: 2024-06-29 13:04:46.544290

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fea1dd86bb9c'
down_revision: Union[str, None] = '3d99fc41bf58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('product', sa.Column('extra_review_analyses', sa.JSON(), nullable=True, comment='额外评论分析结果汇总'))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('product', 'extra_review_analyses')
    # ### end Alembic commands ###
