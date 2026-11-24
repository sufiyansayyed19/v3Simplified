from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.internal import router as internal_router
from app.api.v1.parking import router as parking_router
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine, get_db
from app.core.errors import register_exception_handlers
from app.models.parking import seed_default_slots


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    if get_db not in app_instance.dependency_overrides:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_default_slots(db)
    yield


app = FastAPI(title="Corporate Parking — Parking Service", lifespan=lifespan)

register_exception_handlers(app)
app.include_router(parking_router)
app.include_router(internal_router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "service": settings.SERVICE_NAME}
