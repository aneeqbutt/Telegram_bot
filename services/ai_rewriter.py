# AI Rewriter — takes raw article content and turns it into a short Telegram-ready summary.
# Sends the article to the OpenRouter API (configurable model via AI_MODEL env var).
# If the API is unavailable or the key is missing, falls back to truncating the
# original content at the last full sentence within 800 characters.

import httpx
from utils.config import AI_API_KEY, AI_MODEL
from utils.logger import get_logger

logger = get_logger("ai_rewriter")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

PROMPT_TEMPLATE = """You are a crypto news editor for a Telegram channel. Rewrite the article below into a punchy 3-5 sentence summary.

Rules:
- Start with the most important fact
- No clickbait, no filler phrases ("In this article...", "According to...")
- Plain text only — no markdown, no bullet points
- End with one sentence on why this matters for crypto investors
- Maximum 800 characters

Title: {title}

Article:
{content}"""


async def rewrite_article(title: str, content: str) -> str:
    if not AI_API_KEY:
        logger.warning("AI_API_KEY not set — using content truncation fallback")
        return _truncate_fallback(content)

    prompt = PROMPT_TEMPLATE.format(title=title, content=content[:6000])

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                }
            )
            if not response.is_success:
                logger.debug(f"OpenRouter error response ({response.status_code}): {response.text}")
            response.raise_for_status()
            data = response.json()
            rewritten = data["choices"][0]["message"]["content"].strip()
            logger.info(f"AI rewrite successful: {len(rewritten)} chars for '{title[:50]}'")
            return rewritten
    except Exception as e:
        logger.warning(f"AI rewrite failed for '{title[:50]}': {e} — using truncation fallback")
        return _truncate_fallback(content)


def _truncate_fallback(content: str, max_chars: int = 800) -> str:
    if len(content) <= max_chars:
        return content
    truncated = content[:max_chars]
    last_period = truncated.rfind('.')
    if last_period > max_chars // 2:
        return truncated[:last_period + 1]
    return truncated.rstrip() + "..."
