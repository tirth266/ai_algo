import os
import logging
from typing import List, Optional
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # Required Env Vars
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./trades.db")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key-change-me")
    
    # Angel One
    ANGEL_ONE_API_KEY: Optional[str] = os.getenv("ANGEL_ONE_API_KEY")
    ANGEL_ONE_CLIENT_ID: Optional[str] = os.getenv("ANGEL_ONE_CLIENT_ID")
    ANGEL_ONE_SECRET_KEY: Optional[str] = os.getenv("ANGEL_ONE_SECRET_KEY")
    ANGEL_ONE_TOTP_SEED: Optional[str] = os.getenv("ANGEL_ONE_TOTP_SEED")
    ANGEL_ONE_MPIN: Optional[str] = os.getenv("ANGEL_ONE_MPIN")
    
    # Zerodha (Legacy support if needed)
    ZERODHA_API_KEY: Optional[str] = os.getenv("ZERODHA_API_KEY")
    ZERODHA_API_SECRET: Optional[str] = os.getenv("ZERODHA_API_SECRET")

    # App
    PORT: int = int(os.getenv("PORT", 8000))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    def validate_config(self):
        missing = []
        if not self.ANGEL_ONE_API_KEY: missing.append("ANGEL_ONE_API_KEY")
        if not self.ANGEL_ONE_CLIENT_ID: missing.append("ANGEL_ONE_CLIENT_ID")
        if not self.ANGEL_ONE_TOTP_SEED: missing.append("ANGEL_ONE_TOTP_SEED")
        
        if missing:
            logger.warning(f"⚠️ Missing recommended environment variables: {', '.join(missing)}")
            return False
        return True

settings = Settings()
