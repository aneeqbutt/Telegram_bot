# Scraper for CoinTelegraph.
# CoinTelegraph publishes an RSS feed at a fixed URL — a structured XML file that always
# lists their latest 30 articles with titles, URLs, and publish dates.
# Step 1: fetch the RSS XML → parse out 30 article URLs from <link> tags.
# Step 2: visit each article page individually → extract full text from the <article> tag.
# Falls back to the RSS summary text if a page fetch fails or returns too little content.
# Total HTTP calls: 1 RSS request + up to 30 article page requests = 31 calls.

import re
from datetime import datetime
from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper


class CoinTelegraphScraper(BaseScraper):

    async def scrape(self) -> list[dict]:
        # Fetches the RSS feed, then loops through each article to get full content
        self.logger.info("Starting CoinTelegraph scrape via RSS feed...")
        rss_url = "https://cointelegraph.com/rss"

        try:
            rss_html = await self.fetch_page(rss_url)
        except Exception as e:
            self.logger.error(f"Failed to fetch CoinTelegraph RSS feed: {e}")
            return []

        soup = BeautifulSoup(rss_html, "xml")
        items = soup.find_all("item")
        self.logger.info(f"Found {len(items)} items in RSS feed. Processing all...")

        articles = []
        for item in items:
            title = item.find("title").get_text(strip=True) if item.find("title") else "No Title"
            url = item.find("link").get_text(strip=True) if item.find("link") else None
            pub_date_str = item.find("pubDate").get_text(strip=True) if item.find("pubDate") else None

            if not url:
                continue

            # Strip tracking query params from the URL
            url = url.split("?")[0]

            # Parse the publication date from RSS format to a UTC datetime object
            published_at = datetime.utcnow()
            if pub_date_str:
                try:
                    normalized = pub_date_str.replace("GMT", "+0000")
                    published_at = datetime.strptime(normalized, "%a, %d %b %Y %H:%M:%S %z")
                    published_at = published_at.replace(tzinfo=None)
                except Exception as e:
                    self.logger.warning(f"Could not parse pubDate '{pub_date_str}': {e}")

            self.logger.info(f"Fetching article content: {url}")
            content = None
            try:
                # Try fetching the full article page for complete content
                article_html = await self.fetch_page(url)
                content = self._extract_content(article_html)
                if content and len(content) >= 300:
                    self.logger.debug(f"Extracted {len(content)} chars from article page: {url}")
                else:
                    if content:
                        self.logger.debug(f"Content too short ({len(content)} chars) from page {url} — using RSS fallback")
                    content = None
            except Exception as e:
                self.logger.warning(f"Failed to fetch article page {url} ({e}). Trying feed summary fallback...")

            if not content:
                # RSS fallback: use the summary/description tag from the feed entry
                feed_content_tag = item.find("content") or item.find("summary") or item.find("description")
                if feed_content_tag:
                    raw_text = feed_content_tag.get_text()
                    content = BeautifulSoup(raw_text, "html.parser").get_text(strip=True)
                    self.logger.info(f"Successfully extracted fallback content from feed for {url}")

            if content:
                articles.append({
                    "title": title,
                    "url": url,
                    "content": content,
                    "published_at": published_at,
                    "source_name": "CoinTelegraph"
                })
            else:
                self.logger.warning(f"No content extracted for {url} even with fallback")

        return articles

    def _extract_content(self, html: str) -> str:
        # Parses the article page HTML and pulls out the main body text.
        # Tries known article container classes first, then falls back to page-wide <p> extraction.
        soup = BeautifulSoup(html, "html.parser")

        container_selectors = [
            lambda s: s.find(class_=lambda x: x and any(term in x for term in ["prose", "post-content", "article__content", "entry-content", "article-content", "post-body"])),
            lambda s: s.find("article"),
            lambda s: s.find("main")
        ]

        paragraphs = []
        for selector in container_selectors:
            container = selector(soup)
            if container:
                paras = container.find_all("p")
                text_blocks = []
                for p in paras:
                    p_text = p.get_text(strip=True)
                    if len(p_text) > 20 and not p_text.startswith(("Related:", "AD:", "Advertisement", "Subscribe to")):
                        text_blocks.append(p_text)
                if len(text_blocks) > 0:
                    paragraphs = text_blocks
                    break

        # Fallback: scan all <p> tags on the page, skipping nav/footer/sidebar parents
        if not paragraphs:
            text_blocks = []
            for p in soup.find_all("p"):
                parent = p.parent
                parent_classes = parent.get("class", []) if parent else []
                parent_class_str = " ".join(parent_classes).lower() if isinstance(parent_classes, list) else str(parent_classes).lower()
                parent_name = parent.name if parent else ""

                if parent_name in ["footer", "header", "nav", "aside"] or any(x in parent_class_str for x in ["footer", "header", "nav", "aside", "sidebar", "comment", "widget", "menu"]):
                    continue

                p_text = p.get_text(strip=True)
                if len(p_text) > 20 and not p_text.startswith(("Related:", "AD:", "Advertisement", "Subscribe to")):
                    text_blocks.append(p_text)
            paragraphs = text_blocks

        return "\n\n".join(paragraphs)
