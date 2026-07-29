"""HTTP routes for SEC filing extraction."""

from fastapi import APIRouter, Depends

from app.controllers.extraction_controller import ExtractionController
from app.repositories.sec_filing_repository import SecFilingRepository
from app.schemas.extraction_schema import (
    ExtractionRequest,
    ExtractionResponse,
)
from app.services.extraction.extraction_service import ExtractionService


router = APIRouter(prefix="/extractions", tags=["extractions"])


def get_extraction_controller() -> ExtractionController:
    return ExtractionController(
        repository=SecFilingRepository(),
        service=ExtractionService(),
    )


@router.post("", response_model=ExtractionResponse)
def extract_filing(
    request: ExtractionRequest,
    controller: ExtractionController = Depends(get_extraction_controller),
) -> ExtractionResponse:
    return controller.extract(request)
