"""add lot_id field

Revision ID: 5fd5d14ef112
Revises: 3b75db0c93a3
Create Date: 2024-07-08 18:28:30.026282

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5fd5d14ef112'
down_revision: Union[str, None] = '3b75db0c93a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('product', sa.Column('lot_id', sa.String(length=128), nullable=True, comment='产品批次 ID'))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('product', 'lot_id')
    # ### end Alembic commands ###
