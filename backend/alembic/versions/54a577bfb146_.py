"""empty message

Revision ID: 54a577bfb146
Revises: 50b096bf85bb
Create Date: 2025-06-25 15:59:31.074968

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "54a577bfb146"
down_revision: Union[str, None] = "50b096bf85bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("message_agent_thoughts", sa.Column("meta", sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("message_agent_thoughts", "meta")
    # ### end Alembic commands ###
