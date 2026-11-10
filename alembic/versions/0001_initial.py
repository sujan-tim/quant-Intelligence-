"""Initial market data and signal tables.

Revision ID: 0001_initial
Revises:
"""

import sqlalchemy as sa

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
    )
    op.create_index("ix_assets_symbol", "assets", ["symbol"], unique=True)
    op.create_table(
        "price_bars",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.UniqueConstraint("asset_id", "date", name="uq_price_bars_asset_date"),
    )
    op.create_index("ix_price_bars_asset_id", "price_bars", ["asset_id"])
    op.create_table(
        "signal_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("rsi_14", sa.Float(), nullable=True),
        sa.Column("macd", sa.Float(), nullable=True),
        sa.Column("macd_signal", sa.Float(), nullable=True),
        sa.Column("sma_20", sa.Float(), nullable=True),
        sa.Column("sma_50", sa.Float(), nullable=True),
        sa.Column("volume_ratio_20", sa.Float(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("asset_id", "date", name="uq_signal_asset_date"),
    )
    op.create_index("ix_signal_snapshots_asset_id", "signal_snapshots", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_signal_snapshots_asset_id", "signal_snapshots")
    op.drop_table("signal_snapshots")
    op.drop_index("ix_price_bars_asset_id", "price_bars")
    op.drop_table("price_bars")
    op.drop_index("ix_assets_symbol", "assets")
    op.drop_table("assets")
