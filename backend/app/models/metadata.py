from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl
from app.core.constants import SourceType

class DocumentMetadata(BaseModel):
    document_id: str
    source: SourceType = SourceType.VBPL
    url: Optional[HttpUrl | None] = None
    so_hieu: Optional[str] = None
    ten_van_ban: Optional[str] = None
    loai_van_ban: Optional[str] = None
    co_quan_ban_hanh: Optional[str] = None
    bo_nganh: Optional[str] = None
    ngay_ban_hanh: Optional[datetime] = None
    hieu_luc_tu: Optional[datetime] = None
    hieu_luc_den: Optional[datetime] = None
    trang_thai_hieu_luc: Optional[str] = None
    so_van_ban_tac_dong: int = 0
    so_van_ban_duoc_tac_dong: int = 0
    content_length: int = 0