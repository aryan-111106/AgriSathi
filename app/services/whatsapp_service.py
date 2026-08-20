import logging
from typing import Optional, List, Dict, Any
import httpx
from app.config import settings

logger = logging.getLogger("agrisaathi.whatsapp")


class WhatsAppService:
    def __init__(self):
        self.token = settings.whatsapp_token
        self.phone_number_id = settings.whatsapp_phone_number_id
        self.api_version = settings.whatsapp_api_version
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.phone_number_id)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    async def send_text_message(self, to_phone: str, text: str, preview_url: bool = False) -> Dict[str, Any]:
        """Send a plain or markdown formatted WhatsApp text message."""
        # Sanitize phone number (strip '+' or spaces)
        clean_phone = to_phone.replace("+", "").replace(" ", "").replace("-", "")
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": text
            }
        }

        if not self.is_configured:
            logger.warning(f"[MOCK SEND] WhatsApp not configured. Message to {clean_phone}: {text[:80]}...")
            return {"status": "mock_sent", "to": clean_phone, "text": text}

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"WhatsApp API error: {e.response.status_code} - {e.response.text}")
                return {"status": "error", "error": e.response.text}
            except Exception as e:
                logger.error(f"Failed to send WhatsApp text message: {e}")
                return {"status": "error", "error": str(e)}

    async def send_interactive_buttons(
        self,
        to_phone: str,
        body_text: str,
        buttons: List[Dict[str, str]],
        header_text: Optional[str] = None,
        footer_text: Optional[str] = "🌾 AgriSaathi — Your AI Farming Partner"
    ) -> Dict[str, Any]:
        """
        Send interactive quick-reply buttons (Max 3 buttons per WhatsApp API rules).
        buttons format: [{"id": "btn_1", "title": "বাংলা"}, {"id": "btn_2", "title": "English"}]
        """
        clean_phone = to_phone.replace("+", "").replace(" ", "").replace("-", "")
        formatted_buttons = []
        for btn in buttons[:3]:  # WhatsApp limits quick-reply buttons to 3
            formatted_buttons.append({
                "type": "reply",
                "reply": {
                    "id": btn["id"],
                    "title": btn["title"][:20]  # WhatsApp max title length 20 chars
                }
            })

        interactive_payload: Dict[str, Any] = {
            "type": "button",
            "body": {"text": body_text},
            "action": {"buttons": formatted_buttons}
        }

        if header_text:
            interactive_payload["header"] = {"type": "text", "text": header_text}
        if footer_text:
            interactive_payload["footer"] = {"text": footer_text}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "interactive",
            "interactive": interactive_payload
        }

        if not self.is_configured:
            logger.warning(f"[MOCK SEND BUTTONS] to {clean_phone}: {body_text} buttons: {[b['title'] for b in buttons]}")
            return {"status": "mock_sent", "to": clean_phone, "buttons": buttons}

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Failed to send interactive buttons: {e}")
                # Fallback to plain text if buttons fail
                fallback_text = f"{body_text}\n\n" + "\n".join([f"👉 {b['title']}" for b in buttons])
                return await self.send_text_message(clean_phone, fallback_text)

    async def send_interactive_list(
        self,
        to_phone: str,
        body_text: str,
        button_label: str,
        sections: List[Dict[str, Any]],
        header_text: Optional[str] = None,
        footer_text: Optional[str] = "🌾 AgriSaathi"
    ) -> Dict[str, Any]:
        """
        Send an interactive WhatsApp List Menu (up to 10 items).
        """
        clean_phone = to_phone.replace("+", "").replace(" ", "").replace("-", "")
        interactive_payload: Dict[str, Any] = {
            "type": "list",
            "body": {"text": body_text},
            "action": {
                "button": button_label[:20],
                "sections": sections
            }
        }

        if header_text:
            interactive_payload["header"] = {"type": "text", "text": header_text}
        if footer_text:
            interactive_payload["footer"] = {"text": footer_text}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "interactive",
            "interactive": interactive_payload
        }

        if not self.is_configured:
            logger.warning(f"[MOCK SEND LIST] to {clean_phone}: {body_text}")
            return {"status": "mock_sent", "to": clean_phone, "list": sections}

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Failed to send interactive list: {e}")
                return await self.send_text_message(clean_phone, body_text)

    async def download_media(self, media_id: str) -> Optional[bytes]:
        """
        Fetch media (images/audio) from WhatsApp Cloud API:
        1. Retrieve media URL from Graph API using media_id.
        2. Download binary bytes with authorization header.
        """
        if not self.is_configured:
            logger.warning(f"[MOCK MEDIA DOWNLOAD] Cannot download media_id {media_id} without configured token.")
            return None

        url = f"{self.base_url}/{media_id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Step 1: Get download URL
                meta_res = await client.get(url, headers=self._get_headers())
                meta_res.raise_for_status()
                media_info = meta_res.json()
                download_url = media_info.get("url")

                if not download_url:
                    return None

                # Step 2: Download raw media bytes
                media_res = await client.get(download_url, headers=self._get_headers())
                media_res.raise_for_status()
                return media_res.content
            except Exception as e:
                logger.error(f"Failed to download WhatsApp media {media_id}: {e}")
                return None

    async def mark_as_read(self, message_id: str) -> bool:
        """Mark incoming WhatsApp message as read with blue ticks."""
        if not self.is_configured:
            return True

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                res = await client.post(url, headers=self._get_headers(), json=payload)
                return res.status_code == 200
            except Exception:
                return False


whatsapp_service = WhatsAppService()
