# Backend

This document explains the backend architecture, responsibilities of each layer, local setup, API usage, and testing workflow for the SEC Form 10-K extraction service.

## Architecture

The backend follows the application flow agreed during design:

```text
Router
  → Controller
      → SEC Filing Repository
      → Extraction Service
          → Layer Extractor
          → Confidence Evaluation
      → API Response
```

The controller is the API use-case coordinator. It asks the repository to prepare the external filing data, passes the resulting `FilingDocument` to the service, and converts the service result into the API response.

The extraction service never downloads data. It starts with a fully prepared `FilingDocument`.

## Folder Structure

```text
backend/
├── main.py
├── app/
│   ├── controllers/
│   │   └── extraction_controller.py
│   ├── routers/
│   │   └── extraction_router.py
│   ├── repositories/
│   │   └── sec_filing_repository.py
│   ├── schemas/
│   │   └── extraction_schema.py
│   ├── models/
│   │   ├── filing_document.py
│   │   └── extraction_result.py
│   ├── services/
│   │   └── extraction/
│   │       ├── extraction_service.py
│   │       └── extractors/
│   │           └── layer1_extractor.py
│   ├── evaluations/
│   │   └── confidence_evaluator.py
│   └── core/
│       ├── config.py
│       └── exceptions.py
├── tests/
│   ├── unit/
│   ├── api/
│   └── integration/
└── requirements.txt
```

## Responsibilities

### Router

- Defines HTTP paths and methods.
- Validates requests through Pydantic schemas.
- Injects the controller.
- Returns the controller response.

The router contains no extraction or data-access logic.

### Controller

- Receives the validated API request.
- Calls the repository to prepare a `FilingDocument`.
- Passes the prepared document to the extraction service.
- Converts `ExtractionResult` into `ExtractionResponse`.

### Repository

- Validates that the URL points to a supported SEC Archives document.
- Performs external HTTP requests.
- Applies SEC request headers and timeouts.
- Detects HTML versus complete-submission TXT.
- Returns a prepared `FilingDocument`.

Only the repository performs external data access.

### Extraction Service

- Starts with a prepared `FilingDocument`.
- Runs Layer 1.
- Calculates filing confidence.
- Will later decide whether to run Layers 2 and 3.
- Returns an internal `ExtractionResult`.

### Layer Extractor

- Contains the extraction algorithm for one layer.
- Performs no HTTP or database access.
- Layer 1 uses regular expressions and `lxml`.

### Evaluation

- Calculates heading, Body-versus-TOC, section, Item, and filing confidence.
- Remains independent from HTTP and repository logic.

## Setup

From the repository root:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
```

## Run

```bash
cd backend
source .venv/bin/activate
python main.py
```

The API is available at:

```text
http://127.0.0.1:8000
```

Interactive documentation:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
GET /health
```

## Extraction Endpoint

```text
POST /api/v1/extractions
```

Request:

```json
{
  "url": "https://www.sec.gov/Archives/edgar/data/21344/000162828026010047/ko-20251231.htm"
}
```

Response:

```json
{
  "confidence": 0.954,
  "layer": "layer1",
  "items": [
    {
      "item": "1",
      "title": "BUSINESS",
      "content": "ITEM 1. BUSINESS ...",
      "content_html": "<p>ITEM 1. BUSINESS</p>...",
      "start": 69388,
      "end": 124745,
      "confidence": {
        "score": 1.0,
        "heading": 1.0,
        "body_vs_toc": 1.0,
        "section": 1.0
      }
    }
  ]
}
```

## Tests

Run tests that do not access the network:

```bash
cd backend
.venv/bin/python -m unittest discover -s tests -v
```

Run live SEC integration tests:

```bash
cd backend
RUN_SEC_INTEGRATION_TESTS=1 \
  .venv/bin/python -m unittest discover -s tests -v
```

Live tests use the two Coca-Cola filings documented in `Extraction.md`.
