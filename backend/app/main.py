from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import SessionLocal, engine
from app.pipeline.run_state import sweep_interrupted_runs
from app.routes import demo as demo_routes
from app.routes import runs as run_routes
from app.routes import search as search_routes
from app.routes import sources as source_routes

logger = logging.getLogger("axiom")

UNHANDLED_ERROR_MESSAGE = "Something went wrong. Check the backend log."


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Fail runs that the previous process left active, then serve."""
    db = SessionLocal()
    try:
        swept = sweep_interrupted_runs(db)
        if swept:
            logger.warning("startup: marked %d interrupted run(s) as failed", swept)
    except Exception:  # noqa: BLE001 - a sweep failure must not stop the app
        db.rollback()
        logger.exception("startup: could not sweep interrupted runs")
    finally:
        db.close()
    yield


app = FastAPI(title="AXIOM", version="0.6.0", lifespan=lifespan)

# Explicit loopback origins only: never a wildcard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(source_routes.router)
app.include_router(search_routes.router)
app.include_router(run_routes.router)
app.include_router(demo_routes.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the traceback server-side and answer with one readable sentence."""
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": UNHANDLED_ERROR_MESSAGE})


@app.get("/health")
def health():
    """Report service status and whether Postgres answers a real query."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "ok", "db": "error"})
    return {"status": "ok", "db": "ok"}
