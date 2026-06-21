import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в .env")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не установлен в .env")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY не установлен в .env")
