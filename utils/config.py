# Central config loader. Reads all environment variables from .env once at import time.
# Every other module imports from here instead of calling os.getenv() directly,
# so if a variable name changes it only needs updating in one place.

from dotenv import load_dotenv
import os

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "telegrambot")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "nex-agi/nex-n2-pro:free")
SCRAPE_INTERVAL_MINUTES = int(os.getenv("SCRAPE_INTERVAL_MINUTES", 60))
MAX_RETRY_COUNT = int(os.getenv("MAX_RETRY_COUNT", 3))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
