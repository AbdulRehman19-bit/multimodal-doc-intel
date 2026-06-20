import asyncio
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
from rank_bm25 import BM25Okapi

from app.config import get_settings
from app.core.colpali_engine import colpali_engine
from app.core.langsmith_tracer import traced

settings = get_settings()


class HybridRetriever:
    """
    Combines ColPali visual embeddings (semantic) with BM25 keyword search.

    Why hybrid?
    - ColPali is great at visual/semantic similarity but can miss exact keywords
    - BM25 is great at exact keyword matching but ignores visual layout
    - Combining both with Reciprocal Rank Fusion (RRF) beats either alone

    RRF formula: score(d) = Σ 1/(k + rank(d))
    where k=60 is a constant that dampens the impact of high rankings.
    This is the same fusion method used in production RAG systems at Elastic.
    """

    def __init__(self, rrf_k: int = 60, alpha: float = 0.5):
        self.rrf_k = rrf_k
        # alpha: weight for ColPali (1-alpha for BM25)
        # 0.5 = equal weight, tune based on your document types
        self.alpha = alpha
        self._bm25_cache: dict[str, BM25Okapi] = {}
        self._corpus_cache: dict[str, list[str]] = {}

    # ── BM25 Index ─────────────────────────────────────────────────────────

    def build_bm25_index(
        self, document_id: str, page_texts: list[str]
    ) -> None:
        """
        Build and cache a BM25 index from extracted page texts.
        page_texts: list of strings, one per page (from OCR or pdfplumber)
        We persist this so we don't re-extract on every restart.
        """
        tokenized = [self._tokenize(text) for text in page_texts]
        bm25 = BM25Okapi(tokenized)

        self._bm25_cache[document_id] = bm25
        self._corpus_cache[document_id] = page_texts

        # Persist to disk alongside the FAISS index
        bm25_path = self._get_bm25_path(document_id)
        with open(bm25_path, "wb") as f:
            pickle.dump({"bm25": bm25, "corpus": page_texts}, f)

    def _load_bm25(self, document_id: str) -> Optional[BM25Okapi]:
        if document_id in self._bm25_cache:
            return self._bm25_cache[document_id]

        bm25_path = self._get_bm25_path(document_id)
        if not bm25_path.exists():
            return None

        with open(bm25_path, "rb") as f:
            data = pickle.load(f)
        self._bm25_cache[document_id] = data["bm25"]
        self._corpus_cache[document_id] = data["corpus"]
        return data["bm25"]

    # ── Hybrid Retrieval ───────────────────────────────────────────────────

    @traced("hybrid_retrieval", tags=["retrieval", "hybrid", "bm25", "colpali"])
    async def retrieve(
        self,
        document_id: str,
        question: str,
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        """
        Run hybrid retrieval and return (page_number, fused_score) pairs.
        Falls back to ColPali-only if BM25 index doesn't exist yet.
        """
        # ColPali retrieval (visual semantic)
        colpali_results = await asyncio.get_event_loop().run_in_executor(
            None,
            colpali_engine.query_index,
            document_id,
            question,
            top_k * 2,  # over-retrieve then re-rank
        )

        # BM25 retrieval (keyword)
        bm25 = self._load_bm25(document_id)
        if bm25 is None:
            # No BM25 index — fall back to ColPali only
            return colpali_results[:top_k]

        bm25_results = self._bm25_retrieve(bm25, question, top_k * 2)

        # Fuse with Reciprocal Rank Fusion
        fused = self._rrf_fuse(colpali_results, bm25_results)
        return fused[:top_k]

    def _bm25_retrieve(
        self, bm25: BM25Okapi, question: str, top_k: int
    ) -> list[tuple[int, float]]:
        """Return (page_number, bm25_score) pairs, 1-indexed."""
        tokens = self._tokenize(question)
        scores = bm25.get_scores(tokens)
        # Get top-k page indices (0-indexed) sorted by score
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(int(idx) + 1, float(scores[idx])) for idx in top_indices]

    def _rrf_fuse(
        self,
        colpali_results: list[tuple[int, float]],
        bm25_results: list[tuple[int, float]],
    ) -> list[tuple[int, float]]:
        """
        Reciprocal Rank Fusion — combines two ranked lists into one.
        Each page gets a score of 1/(k + rank) from each list, summed.
        """
        rrf_scores: dict[int, float] = {}

        for rank, (page_num, _) in enumerate(colpali_results):
            rrf_scores[page_num] = rrf_scores.get(page_num, 0)
            rrf_scores[page_num] += self.alpha * (1 / (self.rrf_k + rank + 1))

        for rank, (page_num, _) in enumerate(bm25_results):
            rrf_scores[page_num] = rrf_scores.get(page_num, 0)
            rrf_scores[page_num] += (1 - self.alpha) * (1 / (self.rrf_k + rank + 1))

        # Sort by fused score
        sorted_pages = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_pages

    def _tokenize(self, text: str) -> list[str]:
        """Simple whitespace + lowercase tokenizer."""
        return text.lower().split()

    def _get_bm25_path(self, document_id: str) -> Path:
        return Path(settings.index_storage_path) / f"{document_id}.bm25"

    def bm25_exists(self, document_id: str) -> bool:
        return self._get_bm25_path(document_id).exists()


hybrid_retriever = HybridRetriever()