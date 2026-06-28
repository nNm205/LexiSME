from app.core.constants import SourceType
from app.core.logging import get_logger
from app.models.raw_document import RawDocument
from app.models.legal_document import LegalDocument
from app.ingestion.parsers.base import BaseParser
from app.ingestion.parsers.html_parser import HTMLParser
from app.ingestion.parsers.pdf_parser import PDFParser
from app.ingestion.parsers.docx_parser import DocxParser

# =====================================================================
# LOGGING
# =====================================================================

logger = get_logger(__name__)

# =====================================================================
# REGISTRY
# =====================================================================

_PARSER_REGISTRY: dict[SourceType, type[BaseParser]] = {
    SourceType.VBPL: HTMLParser,
    SourceType.HTML: HTMLParser, 
    SourceType.PDF:  PDFParser,
    SourceType.DOCX: DocxParser,
}

# =====================================================================
# FACTORY
# =====================================================================

class ParserFactory:
    @staticmethod
    def get_parser(source_type: SourceType) -> BaseParser:
        parser_cls = _PARSER_REGISTRY.get(source_type)
        if parser_cls is None:
            raise ValueError(
                f"Không có parser cho source_type='{source_type}'. "
                f"Các loại được hỗ trợ: {list(_PARSER_REGISTRY.keys())}"
            )
        return parser_cls()

    @staticmethod
    def parse(raw: RawDocument) -> LegalDocument:
        parser = ParserFactory.get_parser(raw.source)
        logger.info(
            "Parsing document_id=%s với %s",
            raw.document_id,
            type(parser).__name__,
        )
        return parser.parse(raw)