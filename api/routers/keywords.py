# API routes for managing classifier keywords (e.g. "bitcoin" → Bitcoin category).
# After every add or delete, the classifier's in-memory cache is reloaded immediately
# so the change takes effect on the very next scrape run without a server restart.
# Mounted at /api/v1/keywords in main.py.

from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from database.db import get_db
from database import crud
from database.models import KeywordCreate
from services.classifier import reload_keywords
from pymongo.errors import DuplicateKeyError

router = APIRouter(prefix="/keywords", tags=["Keywords"])


@router.get("/")
async def list_keywords(category: str = None, db=Depends(get_db)):
    # Returns all keywords, optionally filtered by category name.
    return await crud.get_all_keywords(db, category=category)


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_keyword(keyword: KeywordCreate, db=Depends(get_db)):
    # Creates a new keyword and reloads the classifier cache so it takes effect immediately.
    try:
        result = await crud.insert_keyword(db, keyword.model_dump())
        await reload_keywords(db)
        return result
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Keyword and category combination already exists."
        )


@router.delete("/{keyword_id}")
async def delete_keyword(keyword_id: str, db=Depends(get_db)):
    # Deletes a keyword and reloads the classifier cache so the change takes effect immediately.
    if not ObjectId.is_valid(keyword_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid keyword ID format")
    keywords = await crud.get_all_keywords(db)
    if not any(k["_id"] == keyword_id for k in keywords):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword not found")
    await crud.delete_keyword(db, keyword_id)
    await reload_keywords(db)
    return {"deleted": keyword_id}
