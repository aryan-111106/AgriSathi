"""Outbound message channel abstraction.

Provides a thin interface (`MessageBus`) so the orchestrator and notification
service don't care whether replies go over Telegram, WhatsApp, or anything
else. The active implementation is chosen at construction time based on
`settings.outbound_channel`.
"""

import logging
from typing import Dict, Any, List, Optional, Protocol

from app.config import settings

logger = logging.getLogger("agrisaathi.bus")


class MessageBus(Protocol):
    async def send_text(self, recipient: str, text: str) -> Dict[str, Any]: ...

    async def send_buttons(
        self,
        recipient: str,
        text: str,
        buttons: List[Dict[str, str]],
        header: Optional[str] = None,
        footer: Optional[str] = None,
    ) -> Dict[str, Any]: ...

    async def send_typing(self, recipient: str) -> None: ...

    async def answer_callback(
        self, callback_id: str, text: Optional[str] = None
    ) -> Dict[str, Any]: ...


_bus_instance: Optional[MessageBus] = None


def get_message_bus() -> MessageBus:
    """Lazy singleton accessor."""
    global _bus_instance
    if _bus_instance is not None:
        return _bus_instance

    if settings.outbound_channel == "telegram":
        from app.services.telegram_service import TelegramService

        _bus_instance = TelegramService()  # type: ignore[assignment]
    else:
        from app.services.whatsapp_service import WhatsAppService

        _bus_instance = WhatsAppService()  # type: ignore[assignment]

    logger.info(f"MessageBus initialized with channel={settings.outbound_channel}")
    return _bus_instance


def reset_message_bus_for_tests() -> None:
    """Test helper: drop the cached singleton."""
    global _bus_instance
    _bus_instance = None
