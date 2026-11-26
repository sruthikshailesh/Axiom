from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.db import SessionLocal, engine
from app.pipeline.run_state import sweep_interrupted_runs
from app.routes import auth as auth_routes
from app.routes import dashboard as dashboard_routes
from app.routes import demo as demo_routes
from app.routes import runs as run_routes
from app.routes import search as search_routes
from app.routes import sources as source_routes
from app.routes.auth import require_user

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


app = FastAPI(title="AXIOM", version="0.8.0", lifespan=lifespan)

# Explicit origins from CORS_ORIGINS (two loopback origins by default): never a wildcard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

# Public: GET /health (below) and POST /auth/login. /auth/me checks its own token.
app.include_router(auth_routes.router)

# Everything else needs a signed-in user. The dependency is attached once per
# router, so a new protected route cannot be added without it by accident.
protected = [Depends(require_user)]
app.include_router(source_routes.router, dependencies=protected)
app.include_router(search_routes.router, dependencies=protected)
app.include_router(run_routes.router, dependencies=protected)
app.include_router(demo_routes.router, dependencies=protected)
app.include_router(dashboard_routes.router, dependencies=protected)


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
