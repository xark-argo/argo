"""empty message

Revision ID: c1beb909e1e2
Revises: d998735c8b09
Create Date: 2025-02-27 14:58:15.847100

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1beb909e1e2"
down_revision: Union[str, None] = "d998735c8b09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("models", sa.Column("category", sa.JSON(), nullable=True))
    op.add_column("models", sa.Column("parameter", sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("models", "parameter")
    op.drop_column("models", "category")
    # ### end Alembic commands ###
