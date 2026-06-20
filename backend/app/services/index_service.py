import asyncio
from PIL import Image

from app.core.colpali_engine import colpali_engine
from app.core.pdf_processor import pdf_processor
from app.core.hybrid_retriever import hybrid_retriever
from app.core.reranker import reranker
from app.core.langsmith_tracer import traced
from app.services.document_service import document_service


class IndexService:
    """
    Orchestrates the full document ingestion pipeline:
    PDF → page images → ColPali FAISS index + BM25 text index

    Both indexes are built in parallel so hybrid retrieval works
    from the first query without any extra steps.
    """

    @traced("build_document_index", tags=["indexing", "colpali", "bm25"])
    async def build_index_for_document(self, document_id: str) -> dict:
        doc = await self._get_document_or_raise(document_id)
        pdf_bytes = await document_service.download_pdf_from_storage(
            doc.storage_path
        )

        page_images: list[Image.Image] = []
        page_texts: list[str] = []

        for page_num, raw_image in pdf_processor.pdf_to_images_generator(pdf_bytes):
            image = pdf_processor.resize_for_model(raw_image)
            page_images.append(image)

            # Extract text for BM25 (best-effort; empty string if scan)
            page_text = self._extract_page_text(pdf_bytes, page_num)
            page_texts.append(page_text)

            storage_path = f"{doc.user_id}/pages/{document_id}/page_{page_num}.png"
            image_bytes = pdf_processor.image_to_bytes(image)
            await document_service.store_page_image(
                document_id=document_id,
                page_number=page_num,
                image_bytes=image_bytes,
                storage_path=storage_path,
            )

        # Build ColPali FAISS index
        index_path = await asyncio.get_event_loop().run_in_executor(
            None,
            colpali_engine.build_index,
            document_id,
            page_images,
        )

        # Build BM25 index from extracted page texts
        if any(page_texts):
            hybrid_retriever.build_bm25_index(document_id, page_texts)

        await document_service.mark_indexed(
            document_id=document_id,
            index_path=index_path,
            page_count=len(page_images),
        )

        return {
            "document_id": document_id,
            "page_count": len(page_images),
            "index_path": index_path,
            "bm25_built": any(page_texts),
        }

    @traced("retrieve_relevant_pages", tags=["retrieval", "hybrid", "rerank"])
    async def retrieve_pages(
        self,
        document_id: str,
        question: str,
        top_k: int = 3,
        use_hybrid: bool = True,
        use_reranker: bool = True,
    ) -> list[dict]:
        """
        Full retrieval pipeline:
        1. Hybrid retrieval (ColPali + BM25 with RRF)
        2. Cross-encoder reranking
        Returns enriched page dicts ready for Gemini.
        """
        if not colpali_engine.index_exists(document_id):
            raise ValueError(f"Document {document_id} has not been indexed yet.")

        if use_hybrid and hybrid_retriever.bm25_exists(document_id):
            results = await hybrid_retriever.retrieve(
                document_id=document_id,
                question=question,
                top_k=top_k * 2,
            )
        else:
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                colpali_engine.query_index,
                document_id,
                question,
                top_k * 2,
            )

        # Enrich with image URLs and page text
        enriched = []
        for page_number, score in results:
            image_url = await document_service.get_page_image_url_by_number(
                document_id=document_id,
                page_number=page_number,
            )
            page_text = self._get_cached_page_text(document_id, page_number)
            enriched.append({
                "document_id": document_id,
                "page_number": page_number,
                "image_url": image_url,
                "relevance_score": score,
                "page_text": page_text,
            })

        # Rerank with cross-encoder
        if use_reranker and enriched:
            enriched = await reranker.rerank(
                question=question,
                candidates=enriched,
                top_k=top_k,
            )
        else:
            enriched = enriched[:top_k]

        return enriched

    def _extract_page_text(self, pdf_bytes: bytes, page_num: int) -> str:
        """Extract text from a PDF page using pdfplumber (best-effort)."""
        try:
            import pdfplumber
            import io
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                if page_num <= len(pdf.pages):
                    text = pdf.pages[page_num - 1].extract_text() or ""
                    return text.strip()
        except Exception:
            pass
        return ""

    def _get_cached_page_text(self, document_id: str, page_number: int) -> str:
        """Get cached page text from BM25 corpus if available."""
        corpus = hybrid_retriever._corpus_cache.get(document_id, [])
        idx = page_number - 1
        if 0 <= idx < len(corpus):
            return corpus[idx]
        return ""

    async def _get_document_or_raise(self, document_id: str):
        from app.services.supabase_client import get_supabase
        db = get_supabase()
        response = (
            db.table("documents")
            .select("*")
            .eq("id", document_id)
            .single()
            .execute()
        )
        if not response.data:
            raise ValueError(f"Document {document_id} not found.")
        from app.models.document import DocumentResponse
        return DocumentResponse(**response.data)


index_service = IndexService()