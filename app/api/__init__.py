from app.api.webhook import router as webhook_router
from app.api.telegram import router as telegram_router
from app.api.chat import router as chat_router
from app.api.farmer import router as farmer_router
from app.api.tools import router as tools_router
from app.api.notifications import router as notifications_router

__all__ = [
    "webhook_router",
    "telegram_router",
    "chat_router",
    "farmer_router",
    "tools_router",
    "notifications_router",
]
