"""Paper account and simulated order history.

Revision ID: 0002_paper_trading
Revises: 0001_initial
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_paper_trading"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("starting_cash", sa.Numeric(18, 2), nullable=False),
        sa.Column("cash", sa.Numeric(18, 2), nullable=False),
    )
    op.create_table(
        "paper_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("paper_accounts.id"), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("execution_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_paper_orders_account_id", "paper_orders", ["account_id"])
    op.create_index("ix_paper_orders_asset_id", "paper_orders", ["asset_id"])
    op.bulk_insert(
        sa.table(
            "paper_accounts",
            sa.column("id", sa.Integer()),
            sa.column("starting_cash", sa.Numeric(18, 2)),
            sa.column("cash", sa.Numeric(18, 2)),
        ),
        [{"id": 1, "starting_cash": 100000, "cash": 100000}],
    )


def downgrade() -> None:
    op.drop_index("ix_paper_orders_asset_id", "paper_orders")
    op.drop_index("ix_paper_orders_account_id", "paper_orders")
    op.drop_table("paper_orders")
    op.drop_table("paper_accounts")
