import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langsmith import traceable

from app.middleware.auth_middleware import verify_supabase_token, get_user_id
from app.models.query import QueryRequest, QueryResponse, RetrievedPage
from app.core.colpali_engine import colpali_engine
from app.core.gemini_client import gemini_client
from app.services.document_service import document_service
from app.services.index_service import index_service
from app.config import get_settings
from PIL import Image
import io, base64, httpx

router = APIRouter(prefix="/query", tags=["query"])
security = HTTPBearer()
settings = get_settings()


@router.post("/", response_model=QueryResponse)
async def query_document(
    request: QueryRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    The main query endpoint — the full multimodal RAG pipeline:

    1. Verify user owns the document
    2. ColPali retrieves the top-k most relevant page images
    3. Gemini 1.5 Flash sees those page images and answers the question
    4. Response includes the answer + retrieved pages + LangSmith trace URL

    Every step is traced in LangSmith for full observability.
    """
    payload = await verify_supabase_token(credentials=credentials)
    user_id = get_user_id(payload)
    document_id = str(request.document_id)

    # Verify document ownership
    doc = await document_service.get_document(document_id, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if not doc.indexed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is still being indexed. Please wait.",
        )

    # Run the traced pipeline
    result = await _run_query_pipeline(
        document_id=document_id,
        question=request.question,
        top_k=request.top_k,
        user_id=user_id,
    )

    return result


@traceable(name="multimodal_rag_pipeline", tags=["rag", "colpali", "gemini"])
async def _run_query_pipeline(
    document_id: str,
    question: str,
    top_k: int,
    user_id: str,
) -> QueryResponse:
    """
    The full pipeline wrapped in a single LangSmith trace.
    Child spans appear for retrieval and VQA steps.
    """

    # Stage 1: ColPali retrieval
    retrieved = await _colpali_retrieve(document_id, question, top_k)

    # Stage 2: Download page images for Gemini (it needs the actual pixels)
    page_images = await _download_page_images(retrieved)

    # Stage 3: Gemini VQA
    answer = await _gemini_vqa(question, page_images, retrieved)

    retrieved_pages = [
        RetrievedPage(
            page_number=r["page_number"],
            image_url=r["image_url"],
            relevance_score=r["relevance_score"],
        )
        for r in retrieved
    ]

    return QueryResponse(
        answer=answer,
        retrieved_pages=retrieved_pages,
        document_id=document_id,
        question=question,
        langsmith_trace_url=None,  # populated by LangSmith callback
    )


@traceable(name="colpali_retrieval", tags=["retrieval"])
async def _colpali_retrieve(
    document_id: str, question: str, top_k: int
) -> list[dict]:
    """ColPali visual retrieval — traced as a child span."""
    return await index_service.retrieve_pages(document_id, question, top_k)


@traceable(name="gemini_vqa", tags=["vqa", "gemini"])
async def _gemini_vqa(
    question: str,
    page_images: list[Image.Image],
    retrieved: list[dict],
) -> str:
    """Gemini visual QA — traced as a child span."""
    page_numbers = [r["page_number"] for r in retrieved]

    # Run sync Gemini call in a thread pool to not block the event loop
    answer = await asyncio.get_event_loop().run_in_executor(
        None,
        gemini_client.answer_with_pages,
        question,
        page_images,
        page_numbers,
    )
    return answer


async def _download_page_images(retrieved: list[dict]) -> list[Image.Image]:
    """
    Fetch the stored page images from Supabase signed URLs.
    Gemini needs the actual image bytes, not just URLs.
    """
    images = []
    async with httpx.AsyncClient() as client:
        for page in retrieved:
            if page["image_url"]:
                response = await client.get(page["image_url"])
                img = Image.open(io.BytesIO(response.content)).convert("RGB")
                images.append(img)
    return images