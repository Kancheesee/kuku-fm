from typing import List
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.schemas.models import IngestPreviewResponse
from app.services.ingest import process_ingestion_payloads

router = APIRouter()


@router.post("/ingest/preview", response_model=IngestPreviewResponse)
async def ingest_preview(
    files: List[UploadFile] = File(...),
) -> IngestPreviewResponse:
    """Preview and parse screenplay files (.txt or .zip) without persisting to database.

    Extracts scenes, timed events, speaker metadata, and validation warnings.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files were provided for ingestion preview.",
        )

    raw_files = []
    for file in files:
        try:
            content = await file.read()
            raw_files.append((file.filename or "unknown.txt", content))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read uploaded file '{file.filename}': {exc}",
            )

    result = process_ingestion_payloads(raw_files)
    return result

