# Telegram Poster — formats and sends messages to the configured Telegram channel.
# Uses raw httpx POST to the Telegram Bot API (no third-party telegram library).
# HTML parse_mode is used instead of MarkdownV2 because crypto titles contain
# special characters that MarkdownV2 requires escaping on every occurrence.
# On a 429 rate limit, reads the exact retry_after value from the API response and waits.

import httpx
import asyncio
from utils.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from utils.logger import get_logger

logger = get_logger("telegram_poster")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

MESSAGE_TEMPLATE = """📰 <b>{title}</b>

{content}

🔗 <a href="{url}">Read full article</a>
📌 Source: {source_name} | 🏷 {category}"""


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_message(title: str, content: str, url: str, source_name: str, category: str) -> str:
    return MESSAGE_TEMPLATE.format(
        title=_escape_html(title),
        content=_escape_html(content),
        url=url,
        source_name=_escape_html(source_name),
        category=_escape_html(category)
    )


async def send_message(text: str, retries: int = 3) -> dict:
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(f"{TELEGRAM_API}/sendMessage", json=payload)
                data = response.json()

            if data.get("ok"):
                logger.info(f"Message sent successfully (message_id: {data['result']['message_id']})")
                return data["result"]

            error_code = data.get("error_code")
            description = data.get("description", "")

            if error_code == 429:
                retry_after = int(description.split("retry after ")[-1]) if "retry after" in description else 30
                logger.warning(f"Telegram rate limit hit — waiting {retry_after}s before retry {attempt}/{retries}")
                await asyncio.sleep(retry_after)
                continue

            raise Exception(f"Telegram API error {error_code}: {description}")

        except httpx.TimeoutException:
            logger.warning(f"Telegram request timed out (attempt {attempt}/{retries})")
            if attempt < retries:
                await asyncio.sleep(5)
            else:
                raise

    raise Exception(f"Failed to send Telegram message after {retries} attempts")
