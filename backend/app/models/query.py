from pydantic import BaseModel, UUID4
from typing import Optional


class QueryRequest(BaseModel):
    document_id: UUID4
    question: str
    top_k: int = 3  # how many pages ColPali retrieves


class RetrievedPage(BaseModel):
    page_number: int
    image_url: str
    relevance_score: float


class QueryResponse(BaseModel):
    answer: str
    retrieved_pages: list[RetrievedPage]
    document_id: UUID4
    question: str
    langsmith_trace_url: Optional[str] = None


class IndexStatusResponse(BaseModel):
    document_id: UUID4
    indexed: bool
    page_count: Optional[int]
    message: str