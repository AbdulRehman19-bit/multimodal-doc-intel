import asyncio
from app.core.colpali_engine import colpali_engine
from app.services.document_service import document_service
from app.core.langsmith_tracer import traced


class MultiDocService:
    """
    Queries multiple document FAISS indexes in parallel,
    merges results, and returns a unified ranked list.

    Flow:
    1. Fan out — query each document's ColPali index concurrently
    2. Merge — collect all (page, score, doc_id) triples into one list
    3. Sort — by relevance score descending
    4. Deduplicate — drop near-duplicate pages from the same document
    5. Return top_k_final pages for Gemini to answer from
    """

    @traced("multi_doc_retrieval", tags=["retrieval", "multi-doc"])
    async def retrieve_across_documents(
        self,
        document_ids: list[str],
        question: str,
        top_k_per_doc: int = 2,
        top_k_final: int = 5,
    ) -> list[dict]:

        # Fan out — query all indexes concurrently
        tasks = [
            self._retrieve_from_one(doc_id, question, top_k_per_doc)
            for doc_id in document_ids
        ]
        results_per_doc = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge all pages into a flat list, skip failed docs
        merged = []
        for doc_id, result in zip(document_ids, results_per_doc):
            if isinstance(result, Exception):
                print(f"Skipping doc {doc_id}: {result}")
                continue
            merged.extend(result)

        # Sort by relevance score
        merged.sort(key=lambda x: x["relevance_score"], reverse=True)

        # Deduplicate: keep best page per (doc_id, page_number) pair
        seen = set()
        deduped = []
        for page in merged:
            key = (page["document_id"], page["page_number"])
            if key not in seen:
                seen.add(key)
                deduped.append(page)

        return deduped[:top_k_final]

    async def _retrieve_from_one(
        self, document_id: str, question: str, top_k: int
    ) -> list[dict]:
        """Query a single document index and enrich with doc metadata."""
        if not colpali_engine.index_exists(document_id):
            raise ValueError(f"Document {document_id} not indexed.")

        results = await asyncio.get_event_loop().run_in_executor(
            None,
            colpali_engine.query_index,
            document_id,
            question,
            top_k,
        )

        # Fetch metadata and image URLs
        enriched = []
        for page_number, score in results:
            image_url = await document_service.get_page_image_url_by_number(
                document_id=document_id,
                page_number=page_number,
            )
            enriched.append({
                "document_id": document_id,
                "page_number": page_number,
                "image_url": image_url,
                "relevance_score": score,
            })
        return enriched


multi_doc_service = MultiDocService()