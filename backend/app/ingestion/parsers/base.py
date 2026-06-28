from abc import ABC, abstractmethod
from app.models.raw_document import RawDocument
from app.models.legal_document import LegalDocument

class BaseParser(ABC):
    @abstractmethod
    def parse(self, raw: RawDocument) -> LegalDocument:
        pass