from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from quant_intelligence.settings import get_settings


def test_alembic_builds_current_schema(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'migrated.sqlite3'}"
    monkeypatch.setenv("QIP_DATABASE_URL", database_url)
    get_settings.cache_clear()
    try:
        config = Config("alembic.ini")
        command.upgrade(config, "head")
        command.check(config)
        engine = create_engine(database_url)
        assert {
            "assets",
            "price_bars",
            "signal_snapshots",
            "paper_accounts",
            "paper_orders",
        }.issubset(inspect(engine).get_table_names())
        with engine.connect() as connection:
            assert (
                connection.execute(text("select cash from paper_accounts where id = 1")).scalar()
                == 100000
            )
        engine.dispose()
    finally:
        get_settings.cache_clear()
