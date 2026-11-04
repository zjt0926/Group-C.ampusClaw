import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """集中读取环境变量，密钥只允许从服务端环境注入。"""

    SECRET_KEY = os.getenv("SECRET_KEY", "campusclaw-dev-secret-change-me")
    JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)
    JWT_MAX_AGE = int(os.getenv("JWT_MAX_AGE", str(8 * 60 * 60)))

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///campusclaw.db")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    AI_GATEWAY_BASE_URL = os.getenv("AI_GATEWAY_BASE_URL", "").rstrip("/")
    AI_GATEWAY_API_KEY = os.getenv("AI_GATEWAY_API_KEY", "")
    AI_GATEWAY_MODEL = os.getenv("AI_GATEWAY_MODEL", "gpt-4o-mini")
    AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "90"))

    PASS_SCORE = int(os.getenv("PASS_SCORE", "60"))
    WEB_PORT = int(os.getenv("WEB_PORT", "8000"))
    COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"
