# Pydantic models that define the expected shape of data for each MongoDB collection.
# Used to validate scraper output before it is written to the database,
# and as request body types in the API routers.

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


# Article written by the scraper pipeline
class ArticleCreate(BaseModel):
    url: str
    title: str
    content: str
    source_id: str
    published_at: datetime
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    is_posted: bool = False
    category: str = "Uncategorized"
    rephrased_content: Optional[str] = None


# Sources — the news websites being scraped
class SourceCreate(BaseModel):
    name: str
    base_url: str
    is_active: bool = True

class SourceUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    is_active: Optional[bool] = None


# Categories — topic buckets articles are classified into
class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


# Keywords — words that map to a category for the classifier
class KeywordCreate(BaseModel):
    word: str
    category_name: str
    weight: int = 1


# Channels — Telegram channels the bot posts to
class ChannelCreate(BaseModel):
    name: str
    telegram_id: str
    is_active: bool = True
    post_interval_minutes: int = 60

class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    telegram_id: Optional[str] = None
    is_active: Optional[bool] = None
    post_interval_minutes: Optional[int] = None
