# Postermaking Bot 🎨

A comprehensive **Telegram bot** for generating stunning Anime/Manga posters **and**
Hollywood-style movie/TV thumbnails — powered by **AniList**, **Crunchyroll** and
**TMDB**.

---

## ✨ Features

- **TMDB Integration** — movie / TV search with a "pick the correct title" flow,
  a TMDB poster template, and a Flask micro-service.
- **Magic Thumbnails** — 20 professional templates (Netflix, Disney, HBO, Prime,
  Apple, Cyberpunk, Bollywood, Anime, Horror, K-Drama, Adult ×3, …).
- **Premiere Thumbnails** — 12 cinematic styles (Classic, Netflix, Gold, Neon,
  Minimal, Anime, Horror, K-Drama, Adult ×3, Vintage).
- **AniList / Crunchyroll posters** — the original anime & manga poster templates.
- **Premium tier system** — Bronze / Silver / Gold plans with per-tier daily limits.
- **Per-user settings** — fully callback-driven `/settings` menu (custom brand,
  channel badge, quality tags, default template/style) saved to MongoDB.
- **Group authorization** — owner can `/authorize` / `/unauthorize` chats.
- **Health-check server** — binds `$PORT` so Render/PaaS detect a live service.
- **Modular architecture** — clean separation of `core`, `services`, `plugins`.

---

## 🧱 Project Structure

```
Postermaking-Bot/
├── bot.py                  # entry point (loads config, starts client+health+plugins)
├── config.py               # all settings + .env loading + startup validation
├── main.py                 # optional single-command dev entry
├── start.sh                # loads .env then runs the bot
├── .env.example            # copy this to .env and fill in your secrets
│
├── core/                   # shared application layer
│   ├── logger.py           # centralized logging
│   ├── database.py         # MongoDB wrapper (graceful dummy mode)
│   ├── health.py           # health-check HTTP server
│   └── errors.py           # custom exceptions (TMDBAuthError, …)
│
├── services/               # external integrations
│   ├── tmdb_client.py      # TMDB API client (search + fetch by id)
│   ├── tmdb_service.py     # TMDB Flask micro-service
│   └── upload.py           # ImgBB image upload
│
├── plugins/                # Telegram command/callback handlers
│   ├── start.py            # /start, /help
│   ├── commands.py         # /ani /net /mod /tmdb … poster commands
│   ├── thumbnails.py       # /magic /premiere (callback picker flow)
│   ├── user_settings.py    # /settings (callback-driven, per-user)
│   ├── premium.py          # premium plan commands
│   ├── admin.py            # /authorize /unauthorize /authorized
│   └── broadcast.py        # /broadcast
│
├── templates/              # poster generator engine (Pillow)
├── thumbnail_generator.py  # Magic + Premiere thumbnail engine
├── anilist.py / crunchyroll.py / fonts.py / poster.py
└── fonts/  iconspng/  sc/  tests/
```

> `utils/` and `api/` now contain thin **backward-compatible re-exports** so any
> old import (`from utils.db import db`, `from api.tmdb_client import …`) still works.

---

## 🚀 Deployment

### Prerequisites

- Python 3.9+ (project targets 3.11)
- Telegram bot token from [@BotFather](https://t.me/BotFather)
- `API_ID` + `API_HASH` from [my.telegram.org](https://my.telegram.org)
- A MongoDB database (required for premium / authorize / per-user settings)
- *(Optional)* a TMDB API key / bearer token for `/tmdb`, `/magic`, `/premiere`

### Install

```bash
git clone https://github.com/TELLYHUBCLOUD/Postermaking-Bot.git
cd Postermaking-Bot

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and fill in API_ID, API_HASH, BOT_TOKEN, MONGO_URL, OWNER_ID, TMDB_*
```

### Run

```bash
./start.sh          # loads .env and starts the bot
# or
python bot.py
```

The bot fails fast at startup with a clear message if a required credential is missing.

### Deploy on Render

1. Point Render at this repo, **Build Command**: `pip install -r requirements.txt`,
   **Start Command**: `bash start.sh`.
2. Add the environment variables from `.env.example`.
3. Render reads `$PORT` (auto-set) — the health server binds to it, so the service
   shows as **live** and the bot runs in the same process.

---

## 🎮 Commands

| Command | Description |
|---------|-------------|
| `/start` `/help` | Welcome + help |
| `/ani` `/anim` | AniList Anime / Manga poster |
| `/net` `/netm` | Netflix Anime / Manga poster |
| `/crun` | Crunchyroll poster |
| `/light` `/dark` `/mod` | Simple / Modern posters |
| `/tmdb` `/movie` `/tv` | TMDB Movie / TV poster |
| `/magic <name>` | Magic thumbnail (pick title → pick 1 of 20 templates) |
| `/premiere <name>` | Premiere thumbnail (pick title → pick 1 of 12 styles) |
| `/settings` | Per-user settings via buttons |
| `/my_plan` `/plans` | Premium status / plans |
| Owner: `/broadcast`, `/add_premium`, `/remove_premium`, `/authorize`, `/unauthorize`, `/authorized` |

---

## 🧠 How the thumbnail flow works

```
/magic Inception
   → TMDB search → "Found N matches, select the correct one"
   → 🎬 Inception (2010)  🎬 Inception (2003) …
   → pick a template (Classic, Netflix, Disney, …)
   → downloads backdrop+poster → renders → sends the image
```

If a user set a **default template/style** in `/settings`, the picker is skipped
and their preferred style is used automatically.

---

## 🔧 Configuration (`.env`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `API_ID`, `API_HASH`, `BOT_TOKEN` | ✅ | Telegram bot |
| `MONGO_URL` | ✅ | Database for premium/authorize/settings |
| `OWNER_ID` | ✅ | Owner Telegram ID (admin commands) |
| `TMDB_BEARER_TOKEN` / `TMDB_API_KEY` | for TMDB features | Movie/TV data |
| `THUMBNAIL_BRAND`, `THUMBNAIL_CHANNEL`, `THUMBNAIL_QUALITY_TAGS` | optional | Thumbnail defaults |
| `LIMIT_DEFAULT/BRONZE/SILVER/GOLD` | optional | Per-tier daily limits |
| `PORT` | Render auto-set | Health server port |

---

## 💬 Credits

- **Powered by:** @Blaze_Updatez
- **Created by:** @Bharath_boy
