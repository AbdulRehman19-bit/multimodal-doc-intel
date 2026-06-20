# DocLens — Multimodal Document Intelligence

Visual RAG pipeline using **ColPali** embeddings + **Gemini 1.5 Flash** for question answering over PDFs with tables, charts, and scanned pages.

## Stack

| Layer | Tech |
|---|---|
| Visual Embeddings | ColPali (vidore/colpali-v1.2) via byaldi |
| Vector Store | FAISS (CPU, no GPU needed) |
| Vision QA | Google Gemini 1.5 Flash (free tier) |
| Observability | LangSmith (free tier) |
| Auth + Storage | Supabase |
| Backend | FastAPI + Python 3.11 |
| Frontend | React + Vite + Tailwind |

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Fill in your keys: Supabase, Gemini API, LangSmith

# 2. Run Supabase schema
# Paste supabase/schema.sql into your Supabase SQL editor
# Paste supabase/storage_policies.sql into your Supabase SQL editor

# 3. Run with Docker
docker-compose up --build

# Or run manually:
# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

## How it works

Standard RAG extracts text from PDFs then embeds that text. This breaks on tables, charts, and scanned documents.

DocLens takes a different approach:
1. Each PDF page is rendered as a high-resolution image
2. ColPali encodes each page image into a dense embedding — it reads the visual layout directly
3. At query time, the question is embedded and FAISS retrieves the top-k most relevant page images
4. Gemini 1.5 Flash sees those page images and answers the question visually

Every step is traced in LangSmith with child spans for retrieval and VQA.