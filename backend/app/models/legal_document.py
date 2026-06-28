from typing import Optional
from pydantic import BaseModel
from app.models.metadata import DocumentMetadata

class LegalDocument(BaseModel):
    metadata: DocumentMetadata
    content: Optional[str | None] = None 
    content_html: Optional[str | None] = None 
    content_length: int = 0