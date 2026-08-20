"""Telegram Bot API client.

Mirrors the surface area of `whatsapp_service.py` so the rest of the
codebase can talk to either channel through the same `MessageBus` protocol.

Uses raw `httpx.AsyncClient` calls (instead of the full python-telegram-bot
library) to keep the runtime minimal — only the Bot API endpoints we
actually need are exercised.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import httpx

from app.config import settings

logger = logging.getLogger("agrisaathi.telegram")


class TelegramService:
    MAX_MESSAGE_LEN = 4096

    def __init__(self) -> None:
        self.token: Optional[str] = settings.telegram_bot_token
        self.api_base: str = settings.telegram_api_base.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=20.0)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _url(self, method: str) -> str:
        return f"{self.api_base}/bot{self.token}/{method}"

    @staticmethod
    def _split_buttons(
        buttons: List[Dict[str, str]], per_row: int = 2
    ) -> List[List[Dict[str, str]]]:
        """Group flat button list into rows of `per_row` for InlineKeyboard."""
        rows: List[List[Dict[str, str]]] = []
        for i in range(0, len(buttons), per_row):
            row = []
            for b in buttons[i : i + per_row]:
                row.append({"text": b["title"][:64], "callback_data": b["id"][:64]})
            rows.append(row)
        return rows

    @staticmethod
    def _chunk_text(text: str, limit: int) -> List[str]:
        """Telegram has a 4096-char limit; split on newlines if needed."""
        if len(text) <= limit:
            return [text]
        chunks: List[str] = []
        buf = ""
        for line in text.splitlines(keepends=True):
            if len(buf) + len(line) > limit:
                if buf:
                    chunks.append(buf)
                    buf = ""
                while len(line) > limit:
                    chunks.append(line[:limit])
                    line = line[limit:]
                buf = line
            else:
                buf += line
        if buf:
            chunks.append(buf)
        return chunks

    async def _post(self, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_configured:
            logger.warning(
                f"[MOCK TELEGRAM] {method} → chat_id={payload.get('chat_id')} "
                f"text={str(payload.get('text'))[:80]}"
            )
            return {"status": "mock_sent", "method": method, "payload": payload}

        try:
            res = await self.client.post(self._url(method), json=payload)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            logger.error(f"Telegram {method} failed: {e}")
            return {"status": "error", "method": method, "error": str(e)}

    async def send_text(self, chat_id: str, text: str) -> Dict[str, Any]:
        last: Dict[str, Any] = {}
        for chunk in self._chunk_text(text, self.MAX_MESSAGE_LEN):
            payload = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }
            last = await self._post("sendMessage", payload)
        return last

    async def send_buttons(
        self,
        chat_id: str,
        text: str,
        buttons: List[Dict[str, str]],
        header: Optional[str] = None,
        footer: Optional[str] = None,
    ) -> Dict[str, Any]:
        full_text = text
        if header:
            full_text = f"*{header}*\n\n{full_text}"
        if footer:
            full_text = f"{full_text}\n\n_{footer}_"

        reply_markup = {"inline_keyboard": self._split_buttons(buttons)}

        last: Dict[str, Any] = {}
        chunks = self._chunk_text(full_text, self.MAX_MESSAGE_LEN)
        for i, chunk in enumerate(chunks):
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }
            # Only attach keyboard to the last chunk to avoid duplicate buttons
            if i == len(chunks) - 1:
                payload["reply_markup"] = reply_markup
            last = await self._post("sendMessage", payload)
        return last

    async def send_typing(self, chat_id: str) -> None:
        if not self.is_configured:
            return
        try:
            await self._post(
                "sendChatAction", {"chat_id": chat_id, "action": "typing"}
            )
        except Exception as e:
            logger.debug(f"Typing indicator failed: {e}")

    async def answer_callback(
        self, callback_id: str, text: Optional[str] = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text[:200]
        return await self._post("answerCallbackQuery", payload)

    async def download_file(self, file_id: str) -> Optional[bytes]:
        """Resolve a Telegram file_id to its download URL and fetch bytes."""
        if not self.is_configured:
            logger.warning(f"[MOCK DOWNLOAD] file_id={file_id}")
            return None

        try:
            meta = await self._post("getFile", {"file_id": file_id})
            file_path = (meta.get("result") or {}).get("file_path")
            if not file_path:
                return None
            url = f"{self.api_base}/file/bot{self.token}/{file_path}"
            res = await self.client.get(url)
            res.raise_for_status()
            return res.content
        except Exception as e:
            logger.error(f"download_file({file_id}) failed: {e}")
            return None

    async def set_my_commands(self, commands: List[Dict[str, str]]) -> Dict[str, Any]:
        """Register BotFather Menu Button commands.

        Telegram auto-shows a "Menu" button next to the input field; tapping
        it pops up this command list. Telegram picks the localized description
        that matches the user's client language automatically.
        """
        if not self.is_configured:
            logger.info(f"[MOCK setMyCommands] {len(commands)} commands")
            return {"status": "mock_sent", "commands": commands}
        return await self._post("setMyCommands", {"commands": commands})

    async def send_main_keyboard(
        self,
        chat_id: str,
        lang: str = "bn",
    ) -> Dict[str, Any]:
        """Send a persistent ReplyKeyboardMarkup with 9 main-feature buttons
        arranged in a 3x3 grid. Stays visible until farmer hides it manually
        or the bot sends `remove_keyboard`.
        """
        if lang == "bn":
            rows = [
                [{"text": "🌦️ আবহাওয়া"}, {"text": "💰 বাজার দর"}, {"text": "🌱 ফসল পরামর্শ"}],
                [{"text": "📷 রোগ নির্ণয়"}, {"text": "🐛 পোকা নিয়ন্ত্রণ"}, {"text": "🧪 সারের হিসাব"}],
                [{"text": "📊 চাষের খরচ-লাভ"}, {"text": "🏛️ সরকারি প্রকল্প"}, {"text": "👨‍🌾 বিশেষজ্ঞ"}],
            ]
            header = "🌾 AgriSaathi মেনু — যেকোনো বাটন চাপুন অথবা সরাসরি প্রশ্ন লিখুন:"
        else:
            rows = [
                [{"text": "🌦️ Weather"}, {"text": "💰 Mandi Prices"}, {"text": "🌱 Crop Advice"}],
                [{"text": "📷 Disease Diagnosis"}, {"text": "🐛 Pest Control"}, {"text": "🧪 Fertilizer"}],
                [{"text": "📊 Farm Economics"}, {"text": "🏛️ Govt Schemes"}, {"text": "👨‍🌾 Expert"}],
            ]
            header = "🌾 AgriSaathi Menu — tap a button or type your question:"

        payload = {
            "chat_id": chat_id,
            "text": header,
            "reply_markup": {
                "keyboard": rows,
                "resize_keyboard": True,
                "is_persistent": True,
                "selective": False,
            },
        }
        return await self._post("sendMessage", payload)

    async def remove_keyboard(self, chat_id: str, text: str = " ") -> Dict[str, Any]:
        """Hide the persistent reply keyboard for this chat."""
        payload = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": {"remove_keyboard": True, "selective": False},
        }
        return await self._post("sendMessage", payload)


# Module-level BotFather menu definition (9 commands, bilingual descriptions).
# Telegram auto-shows the language that matches the user's client locale.
TELEGRAM_COMMANDS: List[Dict[str, str]] = [
    {"command": "start", "description": "🌾 শুরু / Start — Restart or resume"},
    {"command": "weather", "description": "🌦️ আবহাওয়া / Weather forecast"},
    {"command": "mandi", "description": "💰 বাজার দর / Mandi market prices"},
    {"command": "crop", "description": "🌱 ফসল পরামর্শ / Crop advice"},
    {"command": "disease", "description": "📷 রোগ নির্ণয় / Disease diagnosis"},
    {"command": "pest", "description": "🐛 পোকা নিয়ন্ত্রণ / Pest control"},
    {"command": "fertilizer", "description": "🧪 সারের হিসাব / Fertilizer calculator"},
    {"command": "economy", "description": "📊 চাষের খরচ-লাভ / Farm economics"},
    {"command": "schemes", "description": "🏛️ সরকারি প্রকল্প / Govt schemes"},
    {"command": "expert", "description": "👨‍🌾 বিশেষজ্ঞ / Agricultural expert"},
]


telegram_service = TelegramService()
