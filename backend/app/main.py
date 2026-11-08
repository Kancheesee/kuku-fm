import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.ingest import router as ingest_router
from app.api.promos import router as promos_router
from app.api.runs import router as runs_router
from app.core.session import get_trusted_origins

app = FastAPI(
    title="Kuku Promo Studio API",
    description="Ingestion and promo segment discovery for timestamped microdrama screenplays.",
    version="0.2.0",
)

# CORS setup derived from exact trusted origins (local dev, configured domains, trusted Vercel URLs)
# Wildcards for *.vercel.app are intentionally omitted to prevent cross-origin abuse.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_trusted_origins()),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(ingest_router, prefix="/api", tags=["ingest"])
app.include_router(promos_router, prefix="/api", tags=["promos"])
app.include_router(runs_router, prefix="/api", tags=["runs"])


@app.get("/")
def root():
    return {"message": "Kuku Promo Studio API is running", "docs": "/docs"}

