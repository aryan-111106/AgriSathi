import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    app_name: str = "AgriSaathi"
    app_env: str = "development"
    debug: bool = True
    port: int = 8000
    host: str = "0.0.0.0"

    # WhatsApp Business Cloud API
    whatsapp_token: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_business_account_id: Optional[str] = None
    whatsapp_verify_token: str = "agrisaathi_secure_verify_token_2026"
    whatsapp_api_version: str = "v21.0"

    # Google Gemini AI
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-3.7-flash"

    # Database
    database_url: str = "sqlite+aiosqlite:///./agrisaathi.db"

    # Localization Defaults
    default_language: str = "bn"  # "bn" for Bengali, "en" for English
    default_state: str = "West Bengal"
    default_district: str = "Hooghly"
    default_lat: float = 22.8963
    default_lon: float = 88.2461

    # Weather & External APIs
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"

    # Telegram Bot
    telegram_bot_token: Optional[str] = None
    telegram_webhook_url: Optional[str] = None
    telegram_webhook_secret: str = "agrisaathi_telegram_secret_2026"
    telegram_api_base: str = "https://api.telegram.org"
    outbound_channel: str = "telegram"  # "telegram" or "whatsapp"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
