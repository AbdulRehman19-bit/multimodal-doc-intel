from fastapi import (
    APIRouter, Depends, UploadFile, File,
    HTTPException, BackgroundTasks, status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.middleware.auth_middleware import verify_supabase_token, get_user_id
from app.models.document import DocumentCreate, DocumentResponse, DocumentListResponse
from app.models.query import IndexStatusResponse
from app.services.document_service import document_service
from app.services.index_service import index_service
from app.core.colpali_engine import colpali_engine

router = APIRouter(prefix="/documents", tags=["documents"])
security = HTTPBearer()

ALLOWED_TYPES = {"application/pdf"}
MAX_FILE_SIZE_MB = 50


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Upload a PDF document.
    1. Validates the file
    2. Stores raw PDF in Supabase Storage
    3. Creates a DB record
    4. Triggers ColPali indexing as a background task
    Returns immediately — indexing happens async.
    """
    payload = await verify_supabase_token(credentials=credentials)
    user_id = get_user_id(payload)

    # Validate file type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only PDF files are accepted. Got: {file.content_type}",
        )

    # Read file and check size
    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({size_mb:.1f}MB). Max: {MAX_FILE_SIZE_MB}MB",
        )

    # Upload to Supabase Storage
    storage_path = await document_service.upload_pdf_to_storage(
        file_bytes=file_bytes,
        filename=file.filename,
        user_id=user_id,
    )

    # Create DB record
    doc = await document_service.create_document_record(
        DocumentCreate(
            filename=file.filename,
            user_id=user_id,
            storage_path=storage_path,
        )
    )

    # Kick off indexing in the background
    background_tasks.add_task(
        index_service.build_index_for_document,
        str(doc.id),
    )

    return doc


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Return all documents for the authenticated user."""
    payload = await verify_supabase_token(credentials=credentials)
    user_id = get_user_id(payload)

    docs = await document_service.list_documents(user_id)
    return DocumentListResponse(documents=docs, total=len(docs))


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get a single document by ID."""
    payload = await verify_supabase_token(credentials=credentials)
    user_id = get_user_id(payload)

    doc = await document_service.get_document(document_id, user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return doc


@router.get("/{document_id}/index-status", response_model=IndexStatusResponse)
async def get_index_status(
    document_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    payload = await verify_supabase_token(credentials=credentials)
    user_id = get_user_id(payload)

    doc = await document_service.get_document(document_id, user_id)
    if not doc:
        return IndexStatusResponse(
            document_id=document_id,
            indexed=False,
            page_count=None,
            message="Document not found.",
        )

    indexed = colpali_engine.index_exists(document_id)
    return IndexStatusResponse(
        document_id=doc.id,
        indexed=indexed,
        page_count=doc.page_count,
        message="Ready to query." if indexed else "Indexing in progress...",
    )

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Delete a document and its stored files."""
    payload = await verify_supabase_token(credentials=credentials)
    user_id = get_user_id(payload)

    deleted = await document_service.delete_document(document_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")