"""add review analysis field

Revision ID: 04f76a6770d0
Revises: 242e921e8150
Create Date: 2024-06-20 13:40:02.987724

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04f76a6770d0'
down_revision: Union[str, None] = '242e921e8150'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('product', sa.Column('review_summary', sa.String(length=2048), nullable=True, comment='评论总结'))
    op.add_column('product_review', sa.Column('analysis', sa.JSON(), nullable=True, comment='评论分析'))
    op.add_column('product_review', sa.Column('metrics', sa.JSON(), nullable=True, comment='评论指标'))
    op.add_column('product_review', sa.Column('token_usage', sa.JSON(), nullable=True, comment='LLM token 消耗'))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('product_review', 'token_usage')
    op.drop_column('product_review', 'metrics')
    op.drop_column('product_review', 'analysis')
    op.drop_column('product', 'review_summary')
    # ### end Alembic commands ###