# Instagram Telegram Bot

A Telegram bot that downloads Instagram Reels, videos, photos, and carousels from Instagram URLs.

## Features

- Download Instagram Reels/videos
- Download single photos
- Download carousels
- Add the original creator's username as a watermark to videos
- Send downloaded media through Telegram
- Store download history
- Retrieve recent downloads using `/history`
- Help command using `/help`

## Requirements

### Docker

Docker Desktop is recommended.

### Environment

Create a `.env` file based on `.env.example`:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

Never commit or share the `.env` file.

---

# Running with Docker

Build the image:

```powershell
docker build -t instagram-telegram-bot .
```

Run the bot:

```powershell
docker run --rm --env-file .env -v "${PWD}\data:/app/data" -v "${PWD}\downloads:/app/downloads" instagram-telegram-bot
```

The volume mounts preserve:

- `data/` — bot database and persistent data
- `downloads/` — downloaded media

Stop the bot with:

```text
Ctrl+C
```

---

# Running without Docker

Create and activate a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Install Playwright:

```powershell
python -m playwright install chromium
```

Create `.env` from `.env.example` and add the Telegram bot token.

Run:

```powershell
python -m bot.main
```

---

# Project Structure

```text
instagram-telegram-bot/
│
├── bot/
│   └── main.py
│
├── services/
│   └── ...
│
├── utils/
│   └── ...
│
├── data/
│   └── bot.db
│
├── downloads/
│
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
├── requirements.txt
├── test_generator.py
├── test_watermark.py
└── README.md
```

## Important

Do not share:

- `.env`
- Telegram bot token
- private credentials
- downloaded private media

The supplied `.env.example` is only a template.
