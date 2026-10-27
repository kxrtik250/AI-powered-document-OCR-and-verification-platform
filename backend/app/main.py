import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.routes import router
from app.core.config import get_settings
from app.db.session import Base, engine
import app.models  # noqa: F401 - registers SQLAlchemy model metadata

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("documents")}
    additions = {
        "risk_breakdown": "JSON",
        "review_status": "VARCHAR(30) NOT NULL DEFAULT 'not_reviewed'",
        "review_note": "TEXT",
        "reviewed_at": "TIMESTAMP",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE documents ADD COLUMN {name} {definition}"))
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", description="OCR-backed document verification and forensic risk analysis API.", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
