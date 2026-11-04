"""initial schema: 12 张表

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-04
"""
from alembic import op

from app import models  # noqa: F401
from app.extensions import db

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    db.metadata.create_all(bind=bind)


def downgrade():
    bind = op.get_bind()
    db.metadata.drop_all(bind=bind)
