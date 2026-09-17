"""Added table for subtasks

Revision ID: afa76050fc4d
Revises: e4259afd90f2
Create Date: 2026-09-17 18:21:11.108594

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'afa76050fc4d'
down_revision: Union[str, Sequence[str], None] = 'e4259afd90f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
