from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from app.api.v1.vehicles import router as vehicles_router
from app.core.config import settings
from app.core.database import Base, engine, get_db
from app.core.errors import register_exception_handlers
import app.models  # noqa: F401

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
        logger.info("Database tables checked/created successfully.")
    yield
    logger.info("Shutting down %s...", settings.SERVICE_NAME)


app = FastAPI(title="Corporate Parking — Vehicle Service", lifespan=lifespan)

register_exception_handlers(app)
app.include_router(vehicles_router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "service": settings.SERVICE_NAME}
