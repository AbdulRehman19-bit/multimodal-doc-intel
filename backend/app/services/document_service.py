import uuid
from datetime import datetime
from typing import Optional

from app.services.supabase_client import get_supabase
from app.models.document import DocumentCreate, DocumentResponse


class DocumentService:
    """
    Handles all document CRUD operations against Supabase Postgres.
    Supabase Storage is used for the raw PDF files.
    Postgres stores metadata + index paths.
    """

    def __init__(self):
        self.db = get_supabase()
        self.bucket = "documents"

    # ── Storage ────────────────────────────────────────────────────────────

    async def upload_pdf_to_storage(
        self, file_bytes: bytes, filename: str, user_id: str
    ) -> str:
        """
        Upload raw PDF bytes to Supabase Storage.
        Path: documents/{user_id}/{uuid}_{filename}
        Returns the storage path.
        """
        file_id = str(uuid.uuid4())
        storage_path = f"{user_id}/{file_id}_{filename}"

        self.db.storage.from_(self.bucket).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf"},
        )
        return storage_path

    async def download_pdf_from_storage(self, storage_path: str) -> bytes:
        """Download PDF bytes from Supabase Storage for processing."""
        response = self.db.storage.from_(self.bucket).download(storage_path)
        return response

    def get_page_image_url(self, storage_path: str) -> str:
        """Get a signed public URL for a page image stored in Supabase."""
        response = self.db.storage.from_(self.bucket).create_signed_url(
            storage_path, expires_in=3600
        )
        return response["signedURL"]

    # ── Database ───────────────────────────────────────────────────────────

    async def create_document_record(self, doc: DocumentCreate) -> DocumentResponse:
        """Insert a document metadata record into Postgres."""
        data = {
            "id": str(uuid.uuid4()),
            "user_id": doc.user_id,
            "filename": doc.filename,
            "storage_path": doc.storage_path,
            "page_count": doc.page_count,
            "index_path": doc.index_path,
            "indexed": False,
            "created_at": datetime.utcnow().isoformat(),
        }
        response = self.db.table("documents").insert(data).execute()
        return DocumentResponse(**response.data[0])

    async def get_document(
        self, document_id: str, user_id: str
    ) -> Optional[DocumentResponse]:
        """Fetch a single document, scoped to the requesting user."""
        response = (
            self.db.table("documents")
            .select("*")
            .eq("id", document_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if not response.data:
            return None
        return DocumentResponse(**response.data)

    async def list_documents(self, user_id: str) -> list[DocumentResponse]:
        """List all documents belonging to a user, newest first."""
        response = (
            self.db.table("documents")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return [DocumentResponse(**d) for d in response.data]

    async def mark_indexed(
        self, document_id: str, index_path: str, page_count: int
    ) -> None:
        """Mark a document as indexed after ColPali processes it."""
        self.db.table("documents").update(
            {
                "indexed": True,
                "index_path": index_path,
                "page_count": page_count,
            }
        ).eq("id", document_id).execute()

    async def delete_document(self, document_id: str, user_id: str) -> bool:
        """Delete document record and its file from storage."""
        doc = await self.get_document(document_id, user_id)
        if not doc:
            return False

        # Delete from storage
        self.db.storage.from_(self.bucket).remove([doc.storage_path])

        # Delete from DB (cascade deletes pages too via FK)
        self.db.table("documents").delete().eq("id", document_id).execute()
        return True

    # ── Pages ──────────────────────────────────────────────────────────────

    async def store_page_image(
        self,
        document_id: str,
        page_number: int,
        image_bytes: bytes,
        storage_path: str,
    ) -> str:
        """
        Upload a rendered page image to storage and record it in the DB.
        Returns the signed URL for that page image.
        """
        # Upload image to storage
        self.db.storage.from_(self.bucket).upload(
            path=storage_path,
            file=image_bytes,
            file_options={"content-type": "image/png"},
        )

        image_url = self.get_page_image_url(storage_path)

        # Record in document_pages table
        self.db.table("document_pages").insert(
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "page_number": page_number,
                "image_url": image_url,
                "storage_path": storage_path,
            }
        ).execute()

        return image_url

    async def get_page_image_url_by_number(
        self, document_id: str, page_number: int
    ) -> Optional[str]:
        """Look up the stored image URL for a specific page."""
        response = (
            self.db.table("document_pages")
            .select("image_url, storage_path")
            .eq("document_id", document_id)
            .eq("page_number", page_number)
            .single()
            .execute()
        )
        if not response.data:
            return None
        # Refresh the signed URL (they expire after 1 hour)
        return self.get_page_image_url(response.data["storage_path"])


document_service = DocumentService()