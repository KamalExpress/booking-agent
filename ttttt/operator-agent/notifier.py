import os
import requests
import logging

def send_telegram_alert(message: str) -> bool:
    """
    Sends a message via Telegram bot.
    Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to be set in the environment.
    """
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')

    if not bot_token or not chat_id:
        logging.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured. Skipping notification.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logging.info("Telegram notification sent successfully.")
        return True
    except Exception as e:
        logging.error(f"Failed to send Telegram notification: {e}")
        return False

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    send_telegram_alert("🚨 <b>Test Alert</b>: The slot monitor is configured correctly!")
