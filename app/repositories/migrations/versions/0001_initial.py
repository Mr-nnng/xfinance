"""create core tables

Revision ID: 0001
Revises:
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bars",
        sa.Column("symbol", sa.String(length=24), primary_key=True),
        sa.Column("timeframe", sa.String(length=4), primary_key=True),
        sa.Column("adjust", sa.String(length=6), primary_key=True),
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
    )
    op.create_table(
        "securities",
        sa.Column("symbol", sa.String(length=24), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("market", sa.String(length=8), nullable=False),
        sa.Column("board", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "watchlist",
        sa.Column("symbol", sa.String(length=24), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "custom_indices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("expression", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("name", name="uq_custom_indices_name"),
    )
    op.create_table(
        "sync_state",
        sa.Column("key", sa.String(length=96), primary_key=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("note", sa.String(length=128), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sync_state")
    op.drop_table("custom_indices")
    op.drop_table("watchlist")
    op.drop_table("securities")
    op.drop_table("bars")
