import asyncio
import io
import httpx
from PIL import Image

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langsmith import traceable

from app.middleware.auth_middleware import verify_supabase_token, get_user_id
from app.models.query import (
    QueryRequest, QueryResponse, RetrievedPage,
    MultiDocQueryRequest, MultiDocQueryResponse,
    EvalRequest, EvalResult,
)

from app.core.gemini_client import gemini_client
from app.core.evaluator import evaluator
from app.services.document_service import document_service
from app.services.index_service import index_service
from app.services.multi_doc_service import multi_doc_service

router = APIRouter(prefix="/query", tags=["query"])
security = HTTPBearer()


# ── Single document query ──────────────────────────────────────────────────

@router.post("/", response_model=QueryResponse)
async def query_document(
    request: QueryRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Single-document multimodal RAG pipeline:
    ColPali visual retrieval → BM25 hybrid → cross-encoder rerank → Gemini VQA
    Every step traced in LangSmith.
    """
    payload = await verify_supabase_token(credentials=credentials)
    user_id = get_user_id(payload)
    document_id = str(request.document_id)

    doc = await document_service.get_document(document_id, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not doc.indexed:
        raise HTTPException(status_code=409, detail="Document is still being indexed.")

    result = await _run_single_query_pipeline(
        document_id=document_id,
        question=request.question,
        top_k=request.top_k,
        user_id=user_id,
    )
    return result


@traceable(name="single_doc_rag_pipeline", tags=["rag", "colpali", "gemini"])
async def _run_single_query_pipeline(
    document_id: str, question: str, top_k: int, user_id: str
) -> QueryResponse:

    retrieved = await index_service.retrieve_pages(
        document_id=document_id,
        question=question,
        top_k=top_k,
        use_hybrid=True,
        use_reranker=True,
    )

    page_images = await _download_page_images(retrieved)
    answer = await _gemini_vqa(question, page_images, retrieved)

    return QueryResponse(
        answer=answer,
        retrieved_pages=[RetrievedPage(**{
            k: v for k, v in r.items()
            if k in RetrievedPage.model_fields
        }) for r in retrieved],
        document_id=document_id,
        question=question,
    )


# ── Multi-document query ───────────────────────────────────────────────────

@router.post("/multi", response_model=MultiDocQueryResponse)
async def query_multiple_documents(
    request: MultiDocQueryRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Query across multiple documents simultaneously.
    Retrieves from each document's index in parallel, merges results,
    reranks, then sends best pages to Gemini for a unified answer.
    """
    payload = await verify_supabase_token(credentials=credentials)
    user_id = get_user_id(payload)

    document_ids = [str(d) for d in request.document_ids]

    # Verify ownership of all documents
    for doc_id in document_ids:
        doc = await document_service.get_document(doc_id, user_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")
        if not doc.indexed:
            raise HTTPException(status_code=409, detail=f"Document {doc_id} not yet indexed.")

    result = await _run_multi_query_pipeline(
        document_ids=document_ids,
        question=request.question,
        top_k_per_doc=request.top_k_per_doc,
        top_k_final=request.top_k_final,
        user_id=user_id,
    )
    return result


@traceable(name="multi_doc_rag_pipeline", tags=["rag", "multi-doc", "gemini"])
async def _run_multi_query_pipeline(
    document_ids: list[str],
    question: str,
    top_k_per_doc: int,
    top_k_final: int,
    user_id: str,
) -> MultiDocQueryResponse:

    # Fan out retrieval across all documents
    retrieved = await multi_doc_service.retrieve_across_documents(
        document_ids=document_ids,
        question=question,
        top_k_per_doc=top_k_per_doc,
        top_k_final=top_k_final,
    )

    page_images = await _download_page_images(retrieved)
    answer = await _gemini_vqa(question, page_images, retrieved)

    return MultiDocQueryResponse(
        answer=answer,
        retrieved_pages=[RetrievedPage(**{
            k: v for k, v in r.items()
            if k in RetrievedPage.model_fields
        }) for r in retrieved],
        document_ids=document_ids,
        question=question,
    )


# ── Evaluation ─────────────────────────────────────────────────────────────

@router.post("/evaluate", response_model=EvalResult)
async def evaluate_query(
    request: EvalRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Evaluate a RAG response using faithfulness, answer relevancy,
    and context precision — all computed locally with sentence-transformers.
    No paid API needed.

    Use this after a query to score how good the pipeline performed.
    Useful for showing evaluation metrics in your portfolio demo.
    """
    await verify_supabase_token(credentials=credentials)

    scores = await evaluator.evaluate(
        question=request.question,
        answer=request.answer,
        retrieved_pages=[p.dict() for p in request.retrieved_pages],
        ground_truth=request.ground_truth,
    )
    return EvalResult(**scores)


# ── Shared helpers ─────────────────────────────────────────────────────────

@traceable(name="groq_vqa", tags=["vqa", "groq"])
async def _gemini_vqa(
    question: str,
    page_images: list[Image.Image],
    retrieved: list[dict],
) -> str:
    page_numbers = [r["page_number"] for r in retrieved]
    page_texts = [r.get("page_text", "") for r in retrieved]

    return await asyncio.get_event_loop().run_in_executor(
        None,
        gemini_client.answer_with_pages,
        question,
        page_images,
        page_numbers,
        page_texts,
    )


async def _download_page_images(retrieved: list[dict]) -> list[Image.Image]:
    images = []
    async with httpx.AsyncClient() as client:
        for page in retrieved:
            if page.get("image_url"):
                response = await client.get(page["image_url"])
                img = Image.open(io.BytesIO(response.content)).convert("RGB")
                images.append(img)
    return images