import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot.db")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
RSS_CHECK_INTERVAL = 3600
MAX_CHANNELS_PER_USER = 5
MAX_RSS_PER_CHANNEL = 10
DEFAULT_POST_INTERVAL = 7200
MAX_QUEUE_SIZE = 50
AI_MODELS = ["gpt-4o-mini", "gpt-4"]
DEFAULT_AI_MODEL = "gpt-4o-mini"
