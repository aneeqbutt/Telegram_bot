# API routes for reading articles stored by the scraper pipeline.
# Read-only — articles are owned by the pipeline and must not be written via the API
# (writing would bypass cleaning and classification).
# Mounted at /api/v1/articles in main.py.

from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from database.db import get_db
from database import crud

router = APIRouter(prefix="/articles", tags=["Articles"])


@router.get("/")
async def list_articles(
    skip: int = 0,
    limit: int = 20,
    category: str = None,
    is_posted: bool = None,
    db=Depends(get_db)
):
    # Returns a paginated list of articles. Optionally filter by category and/or posted status.
    return await crud.get_articles(db, skip=skip, limit=limit, category=category, is_posted=is_posted)


@router.get("/{article_id}")
async def get_article(article_id: str, db=Depends(get_db)):
    # Returns a single article by its MongoDB ID. Returns 404 if not found.
    if not ObjectId.is_valid(article_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid article ID format")
    article = await crud.get_article_by_id(db, article_id)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return article
