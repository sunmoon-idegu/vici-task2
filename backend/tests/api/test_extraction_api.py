"""FastAPI endpoint tests."""

import unittest

from fastapi.testclient import TestClient

from app.controllers.extraction_controller import ExtractionController
from main import app
from app.models.filing_document import FilingDocument
from app.routers.extraction_router import get_extraction_controller
from app.services.extraction.extraction_service import ExtractionService


SEC_URL = (
    "https://www.sec.gov/Archives/edgar/data/21344/"
    "000162828026010047/ko-20251231.htm"
)


class FakeRepository:
    def fetch(self, url: str) -> FilingDocument:
        return FilingDocument(
            document_type="html",
            content=(
                b"<html><body>"
                b"<div><b>ITEM 1. BUSINESS</b></div>"
                b"<p>" + b"A" * 600 + b"</p>"
                b"<div><b>ITEM 2. PROPERTIES</b></div>"
                b"<p>" + b"B" * 600 + b"</p>"
                b"<div>SIGNATURES</div>"
                b"</body></html>"
            ),
        )


class ExtractionApiTests(unittest.TestCase):
    def setUp(self) -> None:
        controller = ExtractionController(
            repository=FakeRepository(),
            service=ExtractionService(),
        )
        app.dependency_overrides[get_extraction_controller] = (
            lambda: controller
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_extract(self) -> None:
        response = self.client.post(
            "/api/v1/extractions",
            json={"url": SEC_URL},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["layer"], "layer1")
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(
            [item["item"] for item in result["items"]],
            ["1", "2"],
        )
