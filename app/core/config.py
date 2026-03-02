"""
应用配置
"""
import logging
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from pathlib import Path



BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    
    APP_NAME: str
    DEBUG: bool
    API_V1_STR: str
    
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    TEMP_TOKEN_EXPIRE_MINUTES: int
    
    CORS_ORIGINS: List[str]
    
    DB_DIALECT: str = "mysql"  # sqlite / mysql / postgresql
    DATABASE_URL_OVERRIDE: str = Field(default="", alias="DATABASE_URL")
    SQLITE_PATH: str = "./data/app.db"

    DATABASE_HOST: str = ""
    DATABASE_PORT: int = 0
    DATABASE_USER: str = ""
    DATABASE_PASSWORD: str = ""
    DATABASE_NAME: str = ""
    
    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE

        dialect = self.DB_DIALECT.lower().strip()

        if dialect == "sqlite":
            sqlite_path = self.SQLITE_PATH.strip()
            if sqlite_path == ":memory:":
                return "sqlite+aiosqlite:///:memory:"

            path_obj = Path(sqlite_path)
            if path_obj.is_absolute():
                return f"sqlite+aiosqlite:///{path_obj}"
            return f"sqlite+aiosqlite:///{sqlite_path}"

        self._require_database_fields()

        if dialect == "mysql":
            return (
                f"mysql+aiomysql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
                f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
            )
        if dialect in ("postgresql", "postgres", "pg"):
            return (
                f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
                f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
            )

        raise ValueError(
            f"不支持的 DB_DIALECT: {self.DB_DIALECT}，请使用 sqlite/mysql/postgresql"
        )

    def _require_database_fields(self) -> None:
        missing = []
        if not self.DATABASE_HOST:
            missing.append("DATABASE_HOST")
        if not self.DATABASE_PORT:
            missing.append("DATABASE_PORT")
        if not self.DATABASE_USER:
            missing.append("DATABASE_USER")
        if not self.DATABASE_NAME:
            missing.append("DATABASE_NAME")
        if missing:
            raise ValueError(f"数据库配置缺失: {', '.join(missing)}")
    
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_PASSWORD: str
    
    CAPTCHA_LENGTH: int
    CAPTCHA_EXPIRE_SECONDS: int
    EMAIL_CODE_LENGTH: int
    EMAIL_CODE_EXPIRE_SECONDS: int
    
    RATE_LIMIT_CAPTCHA_LIMIT: int
    RATE_LIMIT_CAPTCHA_WINDOW: int
    RATE_LIMIT_EMAIL_CODE_LIMIT: int
    RATE_LIMIT_EMAIL_CODE_WINDOW: int
    RATE_LIMIT_REGISTER_LIMIT: int
    RATE_LIMIT_REGISTER_WINDOW: int
    
    @property
    def RATE_LIMITS(self) -> dict:
        return {
            "captcha": {
                "limit": self.RATE_LIMIT_CAPTCHA_LIMIT,
                "window": self.RATE_LIMIT_CAPTCHA_WINDOW
            },
            "email_code": {
                "limit": self.RATE_LIMIT_EMAIL_CODE_LIMIT,
                "window": self.RATE_LIMIT_EMAIL_CODE_WINDOW
            },
            "register": {
                "limit": self.RATE_LIMIT_REGISTER_LIMIT,
                "window": self.RATE_LIMIT_REGISTER_WINDOW
            }
        }

    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    SMTP_FROM_EMAIL: str
    SMTP_FROM_NAME: str
    
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_SECURE: bool = False
    MINIO_DEFAULT_BUCKET: str = "default"
    
    ES_HOST: str
    ES_USER: str = ""
    ES_PASSWORD: str = ""
    ES_VERIFY_CERTS: bool = False
    ES_DEFAULT_INDEX: str = "default"
    
    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_DEFAULT_TOPIC: str = "default"
    KAFKA_CONSUMER_INSTANCES: int = 2
    KAFKA_PROCESSING_LOCK_TTL_SEC: int = 3600
    KAFKA_IDEMPOTENCY_DONE_TTL_SEC: int = 604800
    KAFKA_DOCUMENT_PARSE_DLQ_TOPIC: str = "document_parse_dlq"
    
    OPENAI_API_KEY: str
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_DIMENSIONS: int = 1536
    
    OPENAI_CHAT_MODEL: str = "gpt-3.5-turbo"
    OPENAI_CHAT_TEMPERATURE: float = 0.7
    OPENAI_CHAT_MAX_TOKENS: int = 2000
    OPENAI_VISION_ENABLED: bool = True
    OPENAI_VISION_MODEL: str = "gpt-4o-mini"
    OPENAI_VISION_MAX_TOKENS: int = 1200
    OPENAI_VISION_MAX_IMAGES_PER_FILE: int = 10
    
    CONVERSATION_MAX_MESSAGES: int = 20
    CONVERSATION_TTL_DAYS: int = 7
    CHAT_STOP_TOKEN_TTL: int = 300
    
    WEBSOCKET_MAX_CONNECTIONS_PER_USER: int = 10
    WEBSOCKET_MAX_CONNECTIONS_PER_INSTANCE: int = 1000
    WEBSOCKET_IDLE_TIMEOUT: int = 3600
    WEBSOCKET_CLEANUP_INTERVAL: int = 300
    
    SEARCH_VECTOR_WEIGHT: float = 0.7
    SEARCH_TEXT_WEIGHT: float = 0.3

    XLSX_SNAPSHOT_NODE_THRESHOLD: int = 6
    XLSX_SNAPSHOT_LOW_TEXT_CHARS_MAX: int = 320
    XLSX_SNAPSHOT_LOW_TOKEN_MAX: int = 120
    XLSX_SNAPSHOT_LOW_CHAR_PER_NON_EMPTY_MAX: float = 8.0
    XLSX_SNAPSHOT_LOW_DISTINCT_TOKEN_MAX: int = 120
    XLSX_SNAPSHOT_LOW_NON_EMPTY_MIN: int = 8
    XLSX_SNAPSHOT_WEAK_MATCH_MIN_SCORE: int = 3
    XLSX_SNAPSHOT_WEAK_MATCH_MIN_LEAD: int = 1
    XLSX_SNAPSHOT_MAX_PAGES_PER_SHEET: int = 3
    
    DEBUG_LOG_LEVEL: str = "DEBUG"
    PRODUCTION_LOG_LEVEL: str = "INFO"
    
    @staticmethod
    def get_log_level() -> int:

        level_str = settings.DEBUG_LOG_LEVEL if settings.DEBUG else settings.PRODUCTION_LOG_LEVEL
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        return level_map.get(level_str.upper(), logging.INFO)
    
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
