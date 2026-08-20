import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db, ensure_schema
from app.api import (
    webhook_router,
    telegram_router,
    chat_router,
    farmer_router,
    tools_router,
    notifications_router,
)

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("agrisaathi.main")


async def _register_telegram_webhook() -> None:
    """If a bot token + public webhook URL are configured, register with Telegram."""
    if not settings.telegram_bot_token or not settings.telegram_webhook_url:
        logger.info("Telegram webhook not configured (set TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_URL).")
        return

    try:
        import httpx
        url = f"{settings.telegram_api_base}/bot{settings.telegram_bot_token}/setWebhook"
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(
                url,
                json={
                    "url": settings.telegram_webhook_url,
                    "secret_token": settings.telegram_webhook_secret,
                    "allowed_updates": ["message", "edited_message", "callback_query"],
                    "drop_pending_updates": True,
                },
            )
            data = res.json()
            if res.status_code == 200 and data.get("ok"):
                logger.info(f"Telegram webhook registered: {settings.telegram_webhook_url}")
            else:
                logger.error(f"Telegram webhook registration failed: {data}")
    except Exception as e:
        logger.error(f"Failed to register Telegram webhook: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing AgriSaathi Database...")
    await init_db()
    await ensure_schema()
    logger.info("AgriSaathi Backend initialized successfully.")
    await _register_telegram_webhook()
    yield
    logger.info("Shutting down AgriSaathi Backend...")


app = FastAPI(
    title=settings.app_name,
    description="WhatsApp AI Farming Assistant with Real-time Mandi, Weather, Vision Disease Diagnosis & Agronomic Intelligence",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(webhook_router)
app.include_router(telegram_router)
app.include_router(chat_router)
app.include_router(farmer_router)
app.include_router(tools_router)
app.include_router(notifications_router)


@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "version": "1.0.0",
        "status": "running",
        "description": "Telegram AI Farming Assistant for Indian & West Bengal Agriculture",
        "languages_supported": ["bn (বাংলা)", "en (English)"],
        "outbound_channel": settings.outbound_channel,
        "endpoints": {
            "telegram_webhook": "/webhook/telegram",
            "whatsapp_webhook": "/webhook/whatsapp",
            "chat_api": "/api/chat",
            "tools_weather": "/api/tools/weather",
            "tools_market": "/api/tools/market",
            "tools_vision": "/api/tools/vision/diagnose",
            "tools_schemes": "/api/tools/schemes",
            "tools_economics": "/api/tools/economics/budget",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "whatsapp_configured": bool(settings.whatsapp_token and settings.whatsapp_phone_number_id),
        "gemini_configured": bool(settings.gemini_api_key),
        "database": "connected"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
