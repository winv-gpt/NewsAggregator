"""Find your Telegram chat ID: send your bot any message first, then run this."""
import requests

from run import load_env
import os

load_env()
token = os.environ.get("TELEGRAM_BOT_TOKEN") or input("Bot token: ").strip()
updates = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20).json()
chats = {u["message"]["chat"]["id"]: u["message"]["chat"].get("first_name") or u["message"]["chat"].get("title")
         for u in updates.get("result", []) if "message" in u}
if not chats:
    print("No messages found. Send your bot a message in Telegram, then run this again.")
for chat_id, name in chats.items():
    print(f"TELEGRAM_CHAT_ID={chat_id}   ({name})")
