from typing import Optional
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel, HttpUrl
from app.core.constants import SourceType

class RawDocument(BaseModel):
    document_id: str
    source: SourceType = SourceType.VBPL
    url: Optional[HttpUrl | None] = None
    file_path: Optional[str | None] = None  
    crawled_at: datetime
    crawl_time_seconds: float
    toan_van_html: Optional[str] = None 
    thuoc_tinh_html: Optional[str] = None 
    luoc_do_html: Optional[str] = None