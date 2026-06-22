# API routes for managing article categories (e.g. Bitcoin, Ethereum, DeFi).
# Supports listing, adding, updating, and deleting categories.
# Mounted at /api/v1/categories in main.py.

from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from database.db import get_db
from database import crud
from database.models import CategoryCreate, CategoryUpdate
from pymongo.errors import DuplicateKeyError

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("/")
async def list_categories(db=Depends(get_db)):
    # Returns all categories in the database.
    return await crud.get_all_categories(db)


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_category(category: CategoryCreate, db=Depends(get_db)):
    # Creates a new category. Returns 409 if a category with the same name already exists.
    try:
        return await crud.insert_category(db, category.model_dump())
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category with this name already exists."
        )


@router.put("/{category_id}")
async def update_category(category_id: str, category: CategoryUpdate, db=Depends(get_db)):
    # Updates the specified fields on an existing category. Returns 404 if not found.
    if not ObjectId.is_valid(category_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category ID format")
    try:
        updated = await crud.update_category(db, category_id, category.model_dump(exclude_unset=True))
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        return updated
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category with this name already exists."
        )


@router.delete("/{category_id}")
async def delete_category(category_id: str, db=Depends(get_db)):
    # Deletes a category by ID. Returns 404 if not found.
    if not ObjectId.is_valid(category_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category ID format")
    categories = await crud.get_all_categories(db)
    if not any(c["_id"] == category_id for c in categories):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    await crud.delete_category(db, category_id)
    return {"deleted": category_id}
