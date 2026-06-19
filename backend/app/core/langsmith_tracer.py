import os
import functools
from typing import Callable, Any
from datetime import datetime

from langsmith import Client
from langsmith.run_helpers import traceable

from app.config import get_settings

settings = get_settings()

# Configure LangSmith env vars (must be set before any langchain imports)
os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langchain_tracing_v2).lower()
os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project

langsmith_client = Client()


def traced(name: str, tags: list[str] | None = None):
    """
    Decorator that wraps any function in a LangSmith trace.
    Use this on any function in the query pipeline so every
    step (embedding, retrieval, VQA) shows up as a child run
    in the LangSmith dashboard.

    Usage:
        @traced("colpali_retrieval", tags=["retrieval"])
        def my_function(...): ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            return await _run_traced(func, name, tags, *args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


async def _run_traced(
    func: Callable, name: str, tags: list[str] | None, *args, **kwargs
) -> Any:
    return await func(*args, **kwargs)


def get_trace_url(run_id: str) -> str | None:
    """
    Build the LangSmith dashboard URL for a specific run.
    This URL is returned to the frontend so users can inspect
    the full trace: ColPali retrieval → Gemini VQA, with timings.
    """
    try:
        project = settings.langchain_project
        return (
            f"https://smith.langchain.com/o/your-org/projects/p/"
            f"{project}/r/{run_id}"
        )
    except Exception:
        return None


class QueryTracer:
    """
    Wraps a complete document query pipeline run as a single LangSmith trace
    with child spans for each stage: retrieval and VQA.
    """

    def __init__(self, document_id: str, question: str, user_id: str):
        self.document_id = document_id
        self.question = question
        self.user_id = user_id
        self.run_id: str | None = None

    @traceable(name="multimodal_query_pipeline")
    async def run(
        self,
        retrieval_fn: Callable,
        vqa_fn: Callable,
    ) -> dict:
        """
        Execute the full pipeline as one traced run:
        1. ColPali retrieval (child span)
        2. Gemini VQA (child span)
        Returns the combined result dict.
        """
        metadata = {
            "document_id": self.document_id,
            "user_id": self.user_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Stage 1: Retrieval
        retrieval_result = await retrieval_fn()

        # Stage 2: VQA
        vqa_result = await vqa_fn(retrieval_result)

        return {
            "retrieval": retrieval_result,
            "answer": vqa_result,
            "metadata": metadata,
        }