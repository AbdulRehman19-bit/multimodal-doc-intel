import asyncio

from app.core.langsmith_tracer import traced


class CrossEncoderReranker:
    """
    Reranks retrieved pages using a cross-encoder model.

    Why rerank?
    - ColPali and BM25 are bi-encoders: they embed query and pages separately.
      This is fast but less precise.
    - A cross-encoder sees (query, page_text) together and scores their
      relevance jointly — much more accurate but slower.
    - We use it as a second-pass filter on the top-k candidates.

    Model: cross-encoder/ms-marco-MiniLM-L-6-v2
    - Runs on CPU, no GPU needed
    - ~22MB download, runs in ~50ms per candidate on CPU
    - Free forever via HuggingFace sentence-transformers
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """Lazy-load the cross-encoder on first use."""
        if self._model is None:
            from sentence_transformers import CrossEncoder
            print(f"Loading reranker: {self.model_name}")
            self._model = CrossEncoder(self.model_name)
            print("Reranker loaded.")

    @traced("cross_encoder_rerank", tags=["reranking"])
    async def rerank(
        self,
        question: str,
        candidates: list[dict],
        top_k: int = 3,
    ) -> list[dict]:
        """
        Rerank a list of candidate pages by relevance to the question.

        candidates: list of dicts with at least 'page_text' and 'page_number'
        Returns the top_k most relevant pages, reordered.

        If a candidate has no page_text (image-only), we use a placeholder
        so ColPali's visual score still influences the final ranking via
        the initial ordering passed in.
        """
        if not candidates:
            return candidates

        self._load_model()

        # Build (question, page_text) pairs for the cross-encoder
        pairs = [
            (question, c.get("page_text") or f"Page {c['page_number']} content")
            for c in candidates
        ]

        # Score in thread pool — cross-encoder inference is CPU-bound
        scores = await asyncio.get_event_loop().run_in_executor(
            None,
            self._model.predict,
            pairs,
        )

        # Attach reranker scores and sort
        for candidate, score in zip(candidates, scores):
            candidate["rerank_score"] = float(score)

        reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

        # Update relevance_score field to reflect reranker output
        for page in reranked:
            page["relevance_score"] = page["rerank_score"]

        return reranked[:top_k]

    def _sigmoid(self, x: float) -> float:
        """Normalize raw cross-encoder logit to 0-1 range."""
        import math
        return 1 / (1 + math.exp(-x))


reranker = CrossEncoderReranker()