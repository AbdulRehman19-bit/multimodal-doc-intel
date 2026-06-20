import re
import asyncio
from typing import Optional

from app.core.langsmith_tracer import traced


class RAGEvaluator:
    """
    Evaluates the RAG pipeline using three metrics — all computed locally,
    no paid API needed.

    Metrics:
    1. Faithfulness — does the answer only say things supported by retrieved pages?
       Score: fraction of answer sentences that can be attributed to context.

    2. Answer Relevancy — does the answer actually address the question?
       Score: cosine similarity between question embedding and answer embedding.

    3. Context Precision — are the retrieved pages actually relevant to the question?
       Score: fraction of retrieved pages that contributed to the answer.

    These are simplified local versions of the RAGAS metrics.
    For a full RAGAS run (requires OpenAI), use the /eval/ragas endpoint.
    """

    def __init__(self):
        self._embedder = None

    def _load_embedder(self):
        """Lazy-load a small sentence-transformer for semantic similarity."""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            # all-MiniLM-L6-v2: 22MB, fast on CPU, good enough for eval
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")

    @traced("rag_evaluation", tags=["evaluation"])
    async def evaluate(
        self,
        question: str,
        answer: str,
        retrieved_pages: list[dict],
        ground_truth: Optional[str] = None,
    ) -> dict:
        """
        Run all three evaluation metrics and return a combined score dict.
        """
        self._load_embedder()

        context_texts = [
            p.get("page_text", "") for p in retrieved_pages if p.get("page_text")
        ]

        faithfulness, answer_relevancy, context_precision = await asyncio.gather(
            self._compute_faithfulness(answer, context_texts),
            self._compute_answer_relevancy(question, answer),
            self._compute_context_precision(question, context_texts),
        )

        overall = (faithfulness + answer_relevancy + context_precision) / 3

        result = {
            "faithfulness": round(faithfulness, 3),
            "answer_relevancy": round(answer_relevancy, 3),
            "context_precision": round(context_precision, 3),
            "overall": round(overall, 3),
        }

        if ground_truth:
            exact_match = self._exact_match(answer, ground_truth)
            result["exact_match"] = exact_match

        return result

    async def _compute_faithfulness(
        self, answer: str, context_texts: list[str]
    ) -> float:
        """
        Faithfulness: fraction of answer sentences attributable to context.
        For each sentence in the answer, check if it's semantically similar
        to at least one context passage.
        """
        if not context_texts:
            return 0.0

        sentences = self._split_sentences(answer)
        if not sentences:
            return 0.0

        full_context = " ".join(context_texts)
        context_emb = await asyncio.get_event_loop().run_in_executor(
            None, self._embedder.encode, [full_context]
        )
        sentence_embs = await asyncio.get_event_loop().run_in_executor(
            None, self._embedder.encode, sentences
        )

        from sklearn.metrics.pairwise import cosine_similarity

        scores = cosine_similarity(sentence_embs, context_emb)
        # A sentence is "faithful" if similarity > 0.5
        faithful_count = sum(1 for s in scores if s[0] > 0.5)
        return faithful_count / len(sentences)

    async def _compute_answer_relevancy(
        self, question: str, answer: str
    ) -> float:
        """
        Answer relevancy: cosine similarity between question and answer embeddings.
        High similarity → the answer is on-topic with the question.
        """
        embs = await asyncio.get_event_loop().run_in_executor(
            None, self._embedder.encode, [question, answer]
        )
        from sklearn.metrics.pairwise import cosine_similarity
        score = cosine_similarity([embs[0]], [embs[1]])[0][0]
        return float(max(0.0, score))

    async def _compute_context_precision(
        self, question: str, context_texts: list[str]
    ) -> float:
        """
        Context precision: fraction of retrieved pages relevant to the question.
        A page is relevant if its embedding is similar enough to the question.
        """
        if not context_texts:
            return 0.0

        question_emb = await asyncio.get_event_loop().run_in_executor(
            None, self._embedder.encode, [question]
        )
        context_embs = await asyncio.get_event_loop().run_in_executor(
            None, self._embedder.encode, context_texts
        )

        from sklearn.metrics.pairwise import cosine_similarity
        scores = cosine_similarity(context_embs, question_emb)
        relevant_count = sum(1 for s in scores if s[0] > 0.4)
        return relevant_count / len(context_texts)

    def _split_sentences(self, text: str) -> list[str]:
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s for s in sentences if len(s.split()) > 3]

    def _exact_match(self, answer: str, ground_truth: str) -> float:
        """Normalized exact match: 1.0 if identical after lowercasing."""
        return float(
            answer.strip().lower() == ground_truth.strip().lower()
        )


evaluator = RAGEvaluator()