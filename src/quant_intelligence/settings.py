from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QIP_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://qip:qip@localhost:5432/qip"
    demo_provider_enabled: bool = True
    rsi_weight: float = Field(default=1.0, ge=0)
    macd_weight: float = Field(default=1.0, ge=0)
    sma_weight: float = Field(default=1.0, ge=0)
    volume_weight: float = Field(default=1.0, ge=0)
    volume_spike_threshold: float = Field(default=2.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
