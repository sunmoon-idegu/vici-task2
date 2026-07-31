"""FastAPI application entry point."""

import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import (
    FilingDownloadError,
    FilingExtractionError,
    InvalidFilingUrlError,
)
from app.routers.extraction_router import router as extraction_router


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.cors_allowed_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(extraction_router, prefix=settings.api_prefix)


@app.head("/health", tags=["health"])
@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}


@app.exception_handler(InvalidFilingUrlError)
async def invalid_url_handler(
    request: Request,
    exc: InvalidFilingUrlError,
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(FilingDownloadError)
async def download_error_handler(
    request: Request,
    exc: FilingDownloadError,
) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(FilingExtractionError)
async def extraction_error_handler(
    request: Request,
    exc: FilingExtractionError,
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=False,
    )
