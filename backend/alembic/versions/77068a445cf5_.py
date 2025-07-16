"""empty message

Revision ID: 77068a445cf5
Revises: 87213f2ccd3b, 37628c2fd6e4
Create Date: 2024-12-09 19:53:23.772681

"""

from collections.abc import Sequence
from typing import Union

# revision identifiers, used by Alembic.
revision: str = "77068a445cf5"
down_revision: Union[str, None] = ("87213f2ccd3b", "37628c2fd6e4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
