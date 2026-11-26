from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from app.api.internal import router as internal_router
from app.api.v1.parking import router as parking_router
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine, get_db
from app.core.errors import register_exception_handlers
from app.models.parking import seed_default_slots

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(settings.SERVICE_NAME)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    logger.info("Starting up %s...", settings.SERVICE_NAME)
    if get_db not in app_instance.dependency_overrides:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_default_slots(db)
        logger.info("Database tables and default parking slots verified.")
    yield
    logger.info("Shutting down %s...", settings.SERVICE_NAME)


app = FastAPI(title="Corporate Parking — Parking Service", lifespan=lifespan)

register_exception_handlers(app)
app.include_router(parking_router)
app.include_router(internal_router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "service": settings.SERVICE_NAME}
