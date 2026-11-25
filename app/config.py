"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite:///./payflow.db"
    TESTING: bool = False
    KAFKA_ENABLED: bool = False
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_TRANSACTIONS: str = "payflow.transactions"
    KAFKA_GROUP_ID: str = "payflow-audit-consumer"
    OUTBOX_BATCH_SIZE: int = 100
    RECONCILIATION_LOOKBACK_DAYS: int = 1


settings = Settings()
