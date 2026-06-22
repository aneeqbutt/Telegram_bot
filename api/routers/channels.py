# API routes for managing Telegram channels the bot posts to.
# Supports listing, adding, updating, and deleting channels.
# Mounted at /api/v1/channels in main.py.

from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from database.db import get_db
from database import crud
from database.models import ChannelCreate, ChannelUpdate
from pymongo.errors import DuplicateKeyError

router = APIRouter(prefix="/channels", tags=["Channels"])


@router.get("/")
async def list_channels(db=Depends(get_db)):
    # Returns all channels in the database.
    return await crud.get_all_channels(db)


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_channel(channel: ChannelCreate, db=Depends(get_db)):
    # Creates a new channel. Returns 409 if a channel with the same Telegram ID already exists.
    try:
        return await crud.insert_channel(db, channel.model_dump())
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Channel with this telegram ID already exists."
        )


@router.put("/{channel_id}")
async def update_channel(channel_id: str, channel: ChannelUpdate, db=Depends(get_db)):
    # Updates the specified fields on an existing channel. Returns 404 if not found.
    if not ObjectId.is_valid(channel_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid channel ID format")
    try:
        updated = await crud.update_channel(db, channel_id, channel.model_dump(exclude_unset=True))
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
        return updated
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Channel with this telegram ID already exists."
        )


@router.delete("/{channel_id}")
async def delete_channel(channel_id: str, db=Depends(get_db)):
    # Deletes a channel by ID. Returns 404 if not found.
    if not ObjectId.is_valid(channel_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid channel ID format")
    channels = await crud.get_all_channels(db)
    if not any(c["_id"] == channel_id for c in channels):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    await crud.delete_channel(db, channel_id)
    return {"deleted": channel_id}
