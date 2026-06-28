from enum import Enum

# ==========================================================
# Source Type (Nguồn dữ liệu)
# ==========================================================
class SourceType(str, Enum):
    VBPL = "vbpl"          # vbpl.vn (website pháp luật Việt Nam)
    PDF = "pdf"            # file PDF nội bộ hoặc upload
    DOCX = "docx"          # file Word
    HTML = "html"          # website HTML khác
    DATABASE = "database"  # dữ liệu từ DB nội bộ

# ==========================================================
# Document Type (Loại văn bản pháp luật)
# ==========================================================
class DocumentType(str, Enum):
    LUAT = "luat"                 # Luật
    NGHI_DINH = "nghi_dinh"       # Nghị định
    THONG_TU = "thong_tu"         # Thông tư
    QUYET_DINH = "quyet_dinh"     # Quyết định
    CHI_THI = "chi_thi"           # Chỉ thị
    CONG_VAN = "cong_van"         # Công văn
    KHAC = "khac"                 # Không xác định / khác