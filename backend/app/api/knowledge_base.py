from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.rag.services.db_rag_ingestion_service import DBRAGIngestionService
from app.database.connection import get_db_session
from app.guardrails.rbac import require_admin

router = APIRouter(
    prefix="/knowledge-base",
    tags=["Knowledge Base"],
)


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".html",
    ".htm",
    ".txt",
    ".md",
}


ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/html",
    "text/plain",
    "text/markdown",
}


@router.post("/upload")
async def upload_knowledge_document(
    file: UploadFile = File(...),
    current_user=Depends(require_admin),
):
    """
    Upload a knowledge-base document and ingest it into Supabase.

    Supported formats:
    - PDF
    - HTML
    - TXT
    - Markdown
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required.",
        )

    original_filename = Path(file.filename).name
    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: {extension}. "
                f"Supported types: {sorted(ALLOWED_EXTENSIONS)}"
            ),
        )

    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported content type: {file.content_type}. "
                f"Supported content types: {sorted(ALLOWED_CONTENT_TYPES)}"
            ),
        )

    temporary_path: Path | None = None

    try:
        # Save uploaded file temporarily.
        with NamedTemporaryFile(
            delete=False,
            suffix=extension,
        ) as temporary_file:

            temporary_path = Path(temporary_file.name)

            shutil.copyfileobj(
                file.file,
                temporary_file,
            )

        # Use the existing DB-backed ingestion pipeline.
        async for session in get_db_session():

            service = DBRAGIngestionService(session)

            result = await service.ingest_file(
                temporary_path,
                original_filename=original_filename,
            )

            return {
                "message": "Knowledge document processed successfully.",
                "filename": original_filename,
                "result": result,
            }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Knowledge document ingestion failed: {exc}",
        ) from exc

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)