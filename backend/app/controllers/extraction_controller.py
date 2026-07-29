"""Controller for the filing extraction API use case."""

from app.repositories.sec_filing_repository import SecFilingRepository
from app.schemas.extraction_schema import (
    ExtractionRequest,
    ExtractionResponse,
)
from app.services.extraction.extraction_service import ExtractionService


class ExtractionController:
    """Prepare service input and convert service output for the router."""

    def __init__(
        self,
        repository: SecFilingRepository,
        service: ExtractionService,
    ) -> None:
        self.repository = repository
        self.service = service

    def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        document = self.repository.fetch(str(request.url))
        result = self.service.extract(document)
        return ExtractionResponse(
            confidence=result.confidence,
            layer=result.layer,
            items=result.items,
        )
