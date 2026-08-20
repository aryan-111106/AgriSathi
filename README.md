# 🌾 AgriSaathi — Telegram AI Farming Assistant

A Telegram AI agricultural assistant for small, medium, and large-scale farmers in West Bengal and India. Real-time mandi prices, weather intelligence, AI crop-disease vision, fertilizer & economics calculators, and government schemes — in **Bengali (বাংলা)** and **English**.

> Migrated from WhatsApp to Telegram for simpler setup, free operation, and richer UI (inline keyboards, persistent reply keyboard, native Markdown, callback queries).

---

## ✨ Features

- **Telegram-native UX** — webhook integration, BotFather Menu Button, persistent 3×3 reply keyboard, inline buttons, callback queries, secret-token verification.
- **Bengali + English + Banglish** — code-switched queries like `কাল weather কেমন থাকবে?` work out of the box.
- **🌦️ Weather** — Open-Meteo 7-day forecast + agrometeorological advisory (rain probability, heatwave, strong wind, disease-risk humidity).
- **💰 Mandi Prices** — distance-aware sorting via Haversine when farmer shares GPS, 7-day price trends.
- **📷 Crop Disease & Pest Diagnosis** — Gemini Vision with image-quality scoring; if confidence < 70%, bot offers interactive button choices (new photo / ask expert / skip).
- **🧪 Fertilizer Calculator** — calibrated N-P-K per Bigha/Acre for Rice, Potato, Mustard, Tomato, Brinjal, Jute.
- **📊 Farm Economics** — itemized input costs, projected revenue, net profit, ROI; crop-vs-crop comparison.
- **🏛️ Government Schemes** — Krishak Bandhu, PM-Kisan, Bangla Shasya Bima, Soil Health Card, SMAM/CHC.
- **🛡️ Safety & Escalation** — banned-chemical filter, PPE warnings, direct line to Kisan Call Center (`1800-180-1551`) and Block ADA officers.
- **🔔 Notification Preferences** — opt-in toggles, quiet hours, 12h cooldown.
- **🧹 Privacy** — `DELETE /api/farmer/{phone}` cascade + image-wipe endpoint; conditional image storage.
- **🎙️ Voice Notes** — Gemini STT for Bengali/English voice messages.

---

## 🏗️ Architecture

```
🌾 Farmer (Telegram)
       │ Text/Voice/Photo/Location/Button
       ▼
Telegram Bot Platform  →  POST /webhook/telegram
       ▼
FastAPI Backend  →  AI Orchestrator
       ▼
┌──────────┬──────────┬──────────┬──────────┬──────────┐
│ Weather  │  Mandi   │  Vision  │  Agronomy│Economics │
│ Service  │  Tool    │  Disease │   RAG    │+ Schemes │
└──────────┴──────────┴──────────┴──────────┴──────────┘
       ▼
MessageBus (Telegram default / WhatsApp swappable)
       ▼
🌾 Farmer's Telegram
```

---

## 🛠️ Quick Start

### 1. Prerequisites
- Python 3.10+
- Telegram bot token (from [@BotFather](https://t.me/BotFather))
- Gemini API key (optional, for vision + voice)
- ngrok (for local dev webhook exposure)

### 2. Install & configure
```powershell
cd D:\Programs\Vibe Coding\KrishiSathi
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_WEBHOOK_URL=https://xxxx.ngrok-free.app/webhook/telegram
GEMINI_API_KEY=AIzaSy...
OUTBOUND_CHANNEL=telegram
DEFAULT_LANGUAGE=bn
```

### 3. Run
```powershell
# Terminal 1
uvicorn app.main:app --reload --port 8000

# Terminal 2
ngrok http 8000
```

The backend lifespan auto-registers the webhook with Telegram on startup.
Open http://localhost:8000/docs for Swagger UI.

### 4. Test on Telegram
1. Find your bot → `/start`
2. Pick **বাংলা** or **English**
3. Walk through onboarding (district → block → village → area → crop → phone)
4. After onboarding: 3×3 reply keyboard + Menu button appear
5. Try: `আজ আলুর দাম কত?` · `আগামীকাল কি বৃষ্টি হবে?` · leaf photo · `কাল weather কেমন থাকবে?` (Banglish)

---

## ✅ Feature Checklist (PRD-Aligned)

Legend: ✅ done · ⏳ planned

| Phase | Status | Notes |
|---|---|---|
| **MVP v1** (§44) — Core Foundation | **20 / 20** ✅ | Telegram webhook, bn/en, onboarding (7 steps), weather, market, vision, voice, RAG, safety |
| **MVP v1.5** (§45) — Engagement & Personalization | **15 / 20** ✅ | Banglish, confidence follow-up, distance sort, notification preferences, economics, schemes, expert escalation, image quality, privacy, conditional storage |
| **Version 2** (§46) — Advanced Intelligence | **0 / 10** ⏳ | Yield prediction, price trends, satellite, more languages, vector RAG, PostgreSQL, Redis |
| **Version 3** (§47) — Platform & Marketplace | **0 / 6** ⏳ | IoT, drone imagery, smart irrigation, marketplace, financing, insurance |
| **Non-Functional** | **1 / 6** ✅ | ✅ auto-migrations · ⏳ Alembic, CI/CD, Sentry, rate limiting, real-farmer pilot |

**Notable ⏳ items in v1.5:** multi-image diagnosis, TTS voice output, crop recovery plan generator, crop calendar with reminders, smart crop recommendation, soil report OCR.

See git history for granular commits tied to each ✅.

---

## 📖 API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/webhook/telegram` | Telegram Bot API inbound updates |
| `POST` | `/webhook/whatsapp` | WhatsApp webhook (fallback channel) |
| `POST` | `/api/chat` | Direct chat for testing |
| `GET` / `PUT` | `/api/farmer/{phone}` | Farmer profile CRUD |
| `POST` | `/api/farmer/{phone}/crops` | Add crop |
| `DELETE` | `/api/farmer/{phone}` | Cascade delete + data wipe |
| `GET` | `/api/tools/weather` | Weather + advisory |
| `GET` | `/api/tools/market` | Mandi prices (lat/lon for distance sort) |
| `POST` | `/api/tools/vision/diagnose` | Disease diagnosis from image |
| `GET` | `/api/tools/schemes` | Government schemes search |
| `POST` | `/api/tools/economics/budget` | Farm budget + ROI |
| `POST` | `/api/tools/economics/compare` | Crop comparison |
| `GET` / `PUT` | `/api/notifications/preferences/{phone}` | Notification opt-ins |

---

## 🧪 Testing

```powershell
pytest -v
```

**70 tests** cover: Telegram webhook + secret verification, Banglish intent classification, BotFather command routing, persistent keyboard resend, image quality scoring, confidence-based disease follow-up, distance-aware market sorting, notification preferences, privacy DELETE endpoints, and the full 7-step onboarding flow.

---

## 🚀 Production Deployment

| Platform | Notes |
|---|---|
| **Render.com** | Free tier; auto-deploy from GitHub; built-in HTTPS |
| **Railway.app** | Free tier; similar to Render |
| **Fly.io** | Free tier; Docker-based |
| **VPS + nginx + certbot** | Full control |

Production `.env`:
```env
TELEGRAM_WEBHOOK_URL=https://agrisaathi.your-domain.com/webhook/telegram
TELEGRAM_WEBHOOK_SECRET=<random-secret>
DEBUG=false
```

When you migrate off SQLite, set `DATABASE_URL=postgresql+asyncpg://...` and add Alembic migrations.

---

## 🔄 Switching Back to WhatsApp

The `MessageBus` abstraction keeps both channels available. To re-enable:
```env
OUTBOUND_CHANNEL=whatsapp
WHATSAPP_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
```

---

## 👥 Contributors

- **AI** — Architecture design, multi-phase implementation (MVP gap closure, Telegram migration, auto-migrations, language UX fixes), test suite, README.
- **You** — Project vision, product decisions, real-world pilot access, ground-truth agricultural knowledge for West Bengal farmers.

Want to contribute? Pick a ⏳ item from the checklist above and open an issue or PR.
