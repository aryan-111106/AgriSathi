import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FarmerProfile, WeatherAlert, MarketWatch, NotificationPreference
from app.services.message_bus import get_message_bus

logger = logging.getLogger("agrisaathi.notifications")


class NotificationService:
    """Proactive weather / market / crop notifications (PRD §33)."""

    @staticmethod
    async def get_or_create_preferences(
        db: AsyncSession, farmer: FarmerProfile
    ) -> NotificationPreference:
        pref = farmer.notification_preferences
        if pref is None:
            pref = NotificationPreference(farmer_phone=farmer.phone)
            db.add(pref)
            await db.commit()
            await db.refresh(pref)
        return pref

    @staticmethod
    def _in_quiet_hours(pref: NotificationPreference, now: datetime) -> bool:
        start = pref.quiet_hours_start
        end = pref.quiet_hours_end
        h = now.hour
        if start == end:
            return False
        if start < end:
            return start <= h < end
        return h >= start or h < end

    @staticmethod
    async def evaluate_weather_alerts(
        db: AsyncSession,
        farmer: FarmerProfile,
        weather_data: Dict[str, Any]
    ) -> List[WeatherAlert]:
        """Convert weather alerts into persisted + queued notifications."""
        pref = await NotificationService.get_or_create_preferences(db, farmer)
        if not pref.weather_alerts_enabled:
            return []

        now = datetime.utcnow()
        if NotificationService._in_quiet_hours(pref, now):
            return []

        queued: List[WeatherAlert] = []
        for alert in weather_data.get("alerts", []) or []:
            row = WeatherAlert(
                farmer_phone=farmer.phone,
                alert_type=alert.get("type", "UNKNOWN"),
                severity="High" if "HEAVY" in (alert.get("type") or "").upper() else "Moderate",
                title_en=alert.get("title_en", "Weather Alert"),
                title_bn=alert.get("title_bn"),
                message_en=alert.get("message_en", ""),
                message_bn=alert.get("message_bn"),
                triggered_at=now,
                source="Open-Meteo Real-time Alert Engine"
            )
            db.add(row)
            queued.append(row)

        if queued:
            await db.commit()
        return queued

    @staticmethod
    async def evaluate_market_alerts(
        db: AsyncSession,
        farmer: FarmerProfile,
        market_results: Dict[str, Any],
        commodity: str
    ) -> List[Dict[str, Any]]:
        """Persist a market alert when the price swing exceeds ±8% (configurable)."""
        pref = await NotificationService.get_or_create_preferences(db, farmer)
        if not pref.market_alerts_enabled:
            return []

        now = datetime.utcnow()
        if NotificationService._in_quiet_hours(pref, now):
            return []

        alerts: List[Dict[str, Any]] = []
        for item in market_results.get("results", [])[:3]:
            trend = item.get("trend_7d_percent", 0.0) or 0.0
            if abs(trend) < 8.0:
                continue

            stmt = select(MarketWatch).where(
                MarketWatch.farmer_phone == farmer.phone,
                MarketWatch.commodity == commodity,
                MarketWatch.district == item.get("district"),
                MarketWatch.is_active == True
            )
            res = await db.execute(stmt)
            watch = res.scalar_one_or_none()

            cooldown_ok = True
            if watch and watch.last_notified_at:
                cooldown_ok = (now - watch.last_notified_at) > timedelta(hours=12)
            if not cooldown_ok:
                continue

            direction_bn = "বেড়েছে" if trend > 0 else "কমেছে"
            direction_en = "risen" if trend > 0 else "fallen"
            icon = "📈" if trend > 0 else "📉"

            payload_bn = (
                f"{icon} {commodity} এর দর গত ৭ দিনে {abs(trend):.1f}% {direction_bn}।\n\n"
                f"📍 {item.get('market_bn', item.get('market'))} ({item.get('district')}): "
                f"₹{item.get('modal_price'):,.0f}/কুইন্টাল"
            )
            payload_en = (
                f"{icon} {commodity} prices have {direction_en} {abs(trend):.1f}% in the last 7 days.\n\n"
                f"📍 {item.get('market')} ({item.get('district')}): "
                f"₹{item.get('modal_price'):,.0f}/quintal"
            )

            if watch:
                watch.current_price = item.get("modal_price", 0)
                watch.baseline_price = watch.baseline_price or watch.current_price
                watch.change_percent = trend
                watch.last_notified_at = now
            else:
                watch = MarketWatch(
                    farmer_phone=farmer.phone,
                    commodity=commodity,
                    district=item.get("district"),
                    state=item.get("state", farmer.state),
                    baseline_price=item.get("modal_price", 0),
                    current_price=item.get("modal_price", 0),
                    change_percent=trend,
                    last_notified_at=now
                )
                db.add(watch)

            alerts.append({
                "phone": farmer.phone,
                "bn": payload_bn,
                "en": payload_en
            })

        if alerts:
            await db.commit()
        return alerts

    @staticmethod
    async def dispatch_text(
        phone: str,
        text_bn: str,
        text_en: str,
        preferred_language: str
    ) -> Dict[str, Any]:
        text = text_bn if preferred_language == "bn" else text_en
        return await get_message_bus().send_text(phone, text)


notification_service = NotificationService()
