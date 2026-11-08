import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.ingest import router as ingest_router

app = FastAPI(
    title="Kuku Promo Studio API",
    description="Ingestion and promo segment discovery for timestamped microdrama screenplays.",
    version="0.1.0",
)

# CORS setup for local development and web previews
cors_origins_env = os.environ.get("CORS_ORIGINS", "")
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if cors_origins_env:
    for o in cors_origins_env.split(","):
        if o.strip() and o.strip() not in origins:
            origins.append(o.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(ingest_router, prefix="/api", tags=["ingest"])


@app.get("/")
def root():
    return {"message": "Kuku Promo Studio API is running", "docs": "/docs"}

