from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import engine
from app.routes import demo as demo_routes
from app.routes import runs as run_routes
from app.routes import search as search_routes
from app.routes import sources as source_routes

app = FastAPI(title="AXIOM", version="0.5.0")

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


@app.get("/health")
def health():
    """Report service status and whether Postgres answers a real query."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "ok", "db": "error"})
    return {"status": "ok", "db": "ok"}
