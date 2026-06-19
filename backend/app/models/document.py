from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional


class DocumentBase(BaseModel):
    filename: str
    page_count: Optional[int] = None


class DocumentCreate(DocumentBase):
    user_id: str
    storage_path: str
    index_path: Optional[str] = None


class DocumentResponse(DocumentBase):
    id: UUID4
    user_id: str
    storage_path: str
    index_path: Optional[str]
    created_at: datetime
    indexed: bool = False

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class DocumentPage(BaseModel):
    id: UUID4
    document_id: UUID4
    page_number: int
    image_url: str