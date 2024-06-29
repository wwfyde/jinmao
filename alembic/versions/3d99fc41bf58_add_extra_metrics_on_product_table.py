"""add extra_metrics on product table

Revision ID: 3d99fc41bf58
Revises: 4bc0d2c3e6de
Create Date: 2024-06-29 12:41:39.016564

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d99fc41bf58'
down_revision: Union[str, None] = '4bc0d2c3e6de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('product', sa.Column('extra_metrics', sa.JSON(), nullable=True, comment='额外评论指标'))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('product', 'extra_metrics')
    # ### end Alembic commands ###
