# Entry point for the FastAPI backend.
# On startup (lifespan): connects to MongoDB, loads keywords into the classifier cache,
# then starts the APScheduler. Everything must boot in that exact order —
# keywords must be in memory before the first scheduler tick fires.
# On shutdown: stops the scheduler and closes the MongoDB connection cleanly.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database.db import connect_db, disconnect_db, get_db
from services.classifier import load_keywords
from scheduler.scheduler import start_scheduler, stop_scheduler
from api.routers import sources, categories, keywords, channels, articles
from api.routers import health, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    db = get_db()
    await load_keywords(db)
    start_scheduler()
    yield
    stop_scheduler()
    await disconnect_db()


app = FastAPI(title="Telegram News Bot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(keywords.router, prefix="/api/v1")
app.include_router(channels.router, prefix="/api/v1")
app.include_router(articles.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(health.router)
