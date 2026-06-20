from pydantic import BaseModel, UUID4
from typing import Optional


class QueryRequest(BaseModel):
    document_id: UUID4
    question: str
    top_k: int = 3


class MultiDocQueryRequest(BaseModel):
    document_ids: list[UUID4]
    question: str
    top_k_per_doc: int = 2      # pages retrieved per document
    top_k_final: int = 5        # pages sent to Gemini after reranking


class RetrievedPage(BaseModel):
    page_number: int
    image_url: str
    relevance_score: float
    document_id: str
    filename: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    retrieved_pages: list[RetrievedPage]
    document_id: UUID4
    question: str
    langsmith_trace_url: Optional[str] = None


class MultiDocQueryResponse(BaseModel):
    answer: str
    retrieved_pages: list[RetrievedPage]
    document_ids: list[UUID4]
    question: str
    langsmith_trace_url: Optional[str] = None


class IndexStatusResponse(BaseModel):
    document_id: UUID4
    indexed: bool
    page_count: Optional[int]
    message: str


class EvalRequest(BaseModel):
    question: str
    answer: str
    retrieved_pages: list[RetrievedPage]
    ground_truth: Optional[str] = None


class EvalResult(BaseModel):
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    overall: float