from typing import Optional
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Railway provides MONGO_URL, so we allow it as an alias for MONGO_URI
    MONGO_URI: str = Field(default="mongodb://localhost:27017", validation_alias=AliasChoices("MONGO_URI", "MONGO_URL"))
    MONGO_DB: str = "strobe"

    # Abuse prevention
    MAX_FLAGS: int = 10_000
    FLAG_TTL_DAYS: int = 90
    RATE_LIMIT_ENABLED: bool = True

    # API key auth (optional)
    API_KEY_ENABLED: bool = False
    API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", populate_by_name=True, extra="ignore")

settings = Settings()
