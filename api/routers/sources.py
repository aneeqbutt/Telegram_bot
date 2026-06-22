# API routes for managing news sources (e.g. CoinTelegraph, Blockworks).
# Supports listing, adding, updating, and deleting sources.
# Mounted at /api/v1/sources in main.py.

from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from database.db import get_db
from database import crud
from database.models import SourceCreate, SourceUpdate
from pymongo.errors import DuplicateKeyError

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("/")
async def list_sources(db=Depends(get_db)):
    # Returns all sources in the database.
    return await crud.get_all_sources(db)


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_source(source: SourceCreate, db=Depends(get_db)):
    # Creates a new source. Returns 409 if a source with the same base URL already exists.
    try:
        return await crud.insert_source(db, source.model_dump())
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source with this base URL already exists."
        )


@router.put("/{source_id}")
async def update_source(source_id: str, source: SourceUpdate, db=Depends(get_db)):
    # Updates the specified fields on an existing source. Returns 404 if not found.
    if not ObjectId.is_valid(source_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid source ID format")
    try:
        updated = await crud.update_source(db, source_id, source.model_dump(exclude_unset=True))
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
        return updated
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source with this base URL already exists."
        )


@router.delete("/{source_id}")
async def delete_source(source_id: str, db=Depends(get_db)):
    # Deletes a source by ID. Returns 404 if not found.
    if not ObjectId.is_valid(source_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid source ID format")
    sources = await crud.get_all_sources(db)
    if not any(s["_id"] == source_id for s in sources):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    await crud.delete_source(db, source_id)
    return {"deleted": source_id}
