from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.config import get_settings
from app.api import auth, documents, query

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: ensure index storage directory exists.
    ColPali model loads lazily on first request to keep startup fast.
    """
    os.makedirs(settings.index_storage_path, exist_ok=True)
    print(f"Index storage ready at: {settings.index_storage_path}")
    yield
    print("Shutting down.")


app = FastAPI(
    title="Multimodal Document Intelligence API",
    description=(
        "Visual document RAG using ColPali embeddings + Gemini 1.5 Flash. "
        "Handles PDFs with tables, charts, and scanned pages natively — "
        "no OCR, no text extraction."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the React frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(query.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}