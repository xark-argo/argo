"""empty message

Revision ID: 027b52c97f1d
Revises: 93f9fea6d9f0
Create Date: 2024-10-31 15:35:04.967629

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "027b52c97f1d"
down_revision: Union[str, None] = "93f9fea6d9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("knowledge", sa.Column("knowledge_status", sa.Integer(), nullable=True))
    op.add_column("knowledge", sa.Column("message", sa.Text(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("knowledge", "message")
    op.drop_column("knowledge", "knowledge_status")
    # ### end Alembic commands ###
