from typing import Optional
from pydantic import BaseModel
from app.models.metadata import DocumentMetadata

class ChunkHierarchy(BaseModel):
    chapter: Optional[str] = None
    section: Optional[str] = None
    article: Optional[int] = None
    clause: Optional[int] = None
    point: Optional[str] = None

class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    chunk_index: int
    hierarchy: ChunkHierarchy
    text: str
    token_count: int
    metadata: DocumentMetadata