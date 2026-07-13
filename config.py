"""
Единая точка загрузки конфигурации из .env.
Все остальные модули импортируют настройки отсюда, а не хардкодят их.
"""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
TRAVELPAYOUTS_TOKEN = os.environ["TRAVELPAYOUTS_TOKEN"]
TRAVELPAYOUTS_MARKER = os.environ["TRAVELPAYOUTS_MARKER"]

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///turkmenbot.db")
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", 4 * 60 * 60))
