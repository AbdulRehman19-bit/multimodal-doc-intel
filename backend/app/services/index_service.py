import asyncio
from PIL import Image

from app.core.colpali_engine import colpali_engine
from app.core.pdf_processor import pdf_processor
from app.core.langsmith_tracer import traced
from app.services.document_service import document_service


class IndexService:
    """
    Orchestrates the full document ingestion pipeline:
    PDF bytes → page images → ColPali embeddings → FAISS index

    This runs as a background task after upload so the API
    returns immediately and processing happens async.
    """

    @traced("build_document_index", tags=["indexing", "colpali"])
    async def build_index_for_document(self, document_id: str) -> dict:
        """
        Full pipeline: download PDF → render pages → build ColPali index.
        Stores page images in Supabase Storage for later retrieval display.
        Returns summary stats.
        """
        # 1. Download PDF from Supabase Storage
        doc = await self._get_document_or_raise(document_id)
        pdf_bytes = await document_service.download_pdf_from_storage(
            doc.storage_path
        )

        # 2. Render each page as an image
        page_images: list[Image.Image] = []
        page_image_urls: list[str] = []

        for page_num, raw_image in pdf_processor.pdf_to_images_generator(pdf_bytes):
            # Resize for ColPali
            image = pdf_processor.resize_for_model(raw_image)
            page_images.append(image)

            # Store page image in Supabase for the frontend to display
            storage_path = f"{doc.user_id}/pages/{document_id}/page_{page_num}.png"
            image_bytes = pdf_processor.image_to_bytes(image)

            image_url = await document_service.store_page_image(
                document_id=document_id,
                page_number=page_num,
                image_bytes=image_bytes,
                storage_path=storage_path,
            )
            page_image_urls.append(image_url)

        # 3. Build ColPali FAISS index from all page images
        # Run in a thread pool since ColPali inference is CPU/GPU bound
        index_path = await asyncio.get_event_loop().run_in_executor(
            None,
            colpali_engine.build_index,
            document_id,
            page_images,
        )

        # 4. Update document record in DB
        await document_service.mark_indexed(
            document_id=document_id,
            index_path=index_path,
            page_count=len(page_images),
        )

        return {
            "document_id": document_id,
            "page_count": len(page_images),
            "index_path": index_path,
        }

    @traced("retrieve_relevant_pages", tags=["retrieval", "colpali"])
    async def retrieve_pages(
        self,
        document_id: str,
        question: str,
        top_k: int = 3,
    ) -> list[dict]:
        """
        Query the ColPali index for a document and return the top-k pages
        with their image URLs and relevance scores.
        """
        if not colpali_engine.index_exists(document_id):
            raise ValueError(
                f"Document {document_id} has not been indexed yet."
            )

        # Get (page_number, score) pairs from ColPali
        results = await asyncio.get_event_loop().run_in_executor(
            None,
            colpali_engine.query_index,
            document_id,
            question,
            top_k,
        )

        # Fetch the stored image URL for each retrieved page
        enriched = []
        for page_number, score in results:
            image_url = await document_service.get_page_image_url_by_number(
                document_id=document_id,
                page_number=page_number,
            )
            enriched.append(
                {
                    "page_number": page_number,
                    "image_url": image_url,
                    "relevance_score": score,
                }
            )

        return enriched

    async def _get_document_or_raise(self, document_id: str):
        # Using service-role client here — called from background task
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