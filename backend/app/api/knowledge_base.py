from __future__ import annotations

import hashlib
import mimetypes
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

# Use your existing auth dependency import here.
from app.api.auth import get_current_user
from app.database.connection import get_db_session
from app.database.models.knowledge import Document, DocumentChunk
from app.database.models.user import User
from app.observability.logging import logger
from app.rag.services.db_rag_ingestion_service import (
    DBRAGIngestionService,
)
from app.rag.services.fusion_retrieval_service import FusionRetrievalService

# ruff: noqa: B008

router = APIRouter(
    prefix="/knowledge-base",
    tags=["Knowledge Base"],
)


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
    ".html",
    ".htm",
}


# ============================================================
# HELPERS
# ============================================================


def document_to_response(
    document: Document,
) -> dict[str, Any]:
    """
    Convert a Document ORM object into a safe API response.

    Original file bytes are intentionally excluded.
    """

    return {
        "id": str(document.id),
        "document_name": document.document_name,
        "document_type": document.document_type,
        "source_url": document.source_url,
        "product_name": document.product_name,
        "product_version": document.product_version,
        "version": document.version,
        "created_at": (
            document.created_at.isoformat() if document.created_at else None
        ),
    }


def _extension_from_document(
    document: Document,
) -> str:
    """
    Resolve the stored file extension.
    """

    document_type = (document.document_type or "").strip().lower()

    if document_type in SUPPORTED_EXTENSIONS:
        return document_type

    suffix = Path(document.document_name).suffix.lower()

    if suffix in SUPPORTED_EXTENSIONS:
        return suffix

    return ""


def _media_type_for_document(
    document: Document,
) -> str:
    """
    Resolve the correct MIME type for browser viewing.
    """

    extension = _extension_from_document(document)

    media_types = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".html": "text/html",
        ".htm": "text/html",
    }

    return media_types.get(
        extension,
        mimetypes.guess_type(document.document_name)[0] or "application/octet-stream",
    )


def _safe_filename(
    filename: str,
) -> str:
    """
    Prevent path-like values from being used
    in Content-Disposition.
    """

    return Path(filename).name or "knowledge-document"


# ============================================================
# LIST DOCUMENTS
# ============================================================


@router.get("/documents")
async def get_knowledge_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """
    Return knowledge-base document metadata.

    File bytes are never returned from this endpoint.
    """

    result = await db.execute(select(Document).order_by(Document.created_at.desc()))

    documents = result.scalars().all()

    return [document_to_response(document) for document in documents]


# ============================================================
# VIEW ORIGINAL DOCUMENT
# ============================================================


@router.get("/documents/{document_id}/file")
async def view_knowledge_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """
    Return the original uploaded knowledge-base file.

    Authenticated customers can view documents.
    Administrators can also view documents.

    The response preserves the original file format.
    """

    result = await db.execute(select(Document).where(Document.id == document_id))

    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge-base document not found.",
        )

    if not document.file_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=("Original uploaded file is not available for this document."),
        )

    media_type = _media_type_for_document(document)

    filename = _safe_filename(document.document_name)

    return Response(
        content=document.file_data,
        media_type=media_type,
        headers={"Content-Disposition": (f'inline; filename="{filename}"')},
    )


# ============================================================
# UPLOAD DOCUMENT
# ============================================================


@router.post(
    "/documents",
    status_code=status.HTTP_201_CREATED,
)
async def upload_knowledge_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Upload a knowledge-base document.

    Supported:
        PDF
        TXT
        Markdown
        HTML
        HTM

    The original file is stored in PostgreSQL as BYTEA.

    The same file is also passed through the existing
    RAG ingestion pipeline.
    """

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=("Only administrators can upload knowledge-base documents."),
        )

    original_filename = Path(file.filename or "").name

    if not original_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A filename is required.",
        )

    extension = Path(original_filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported document type: {extension or 'unknown'}. "
                f"Supported formats: "
                f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )

    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    content_hash = hashlib.sha256(file_bytes).hexdigest()

    existing_result = await db.execute(
        select(Document).where(Document.content_hash == content_hash)
    )

    existing_document = existing_result.scalar_one_or_none()

    if existing_document is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("This knowledge-base document has already been uploaded."),
        )

    document = Document(
        document_name=original_filename,
        document_type=extension,
        source_url=None,
        product_name=None,
        product_version=None,
        version=None,
        content_hash=content_hash,
        file_data=file_bytes,
    )

    db.add(document)

    try:
        await db.flush()

        document_id = document.id

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / original_filename

            temp_path.write_bytes(file_bytes)

            ingestion_service = DBRAGIngestionService(session=db)

            await ingestion_service.ingest_file(
                file_path=str(temp_path),
                document_id=document_id,
                original_filename=original_filename,
            )

        await db.commit()

    except (SQLAlchemyError, ValueError, OSError) as exc:
        await db.rollback()

        logger.exception(
            "Knowledge-base upload failed filename=%s",
            original_filename,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=("Unable to ingest the knowledge-base document."),
        ) from exc

    # --------------------------------------------------------
    # Important:
    # The RAG service caches its retrieval index.
    # A new document must invalidate that cache.
    # --------------------------------------------------------

    try:
        await FusionRetrievalService.invalidate_cache(
            reason="knowledge_document_uploaded"
        )
    except (RuntimeError, TypeError, ValueError, AttributeError):
        logger.exception(
            "RAG cache invalidation failed after document upload document_id=%s",
            document_id,
        )

    return document_to_response(document)


# ============================================================
# DELETE DOCUMENT
# ============================================================


@router.delete(
    "/documents/{document_id}",
)
async def delete_knowledge_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """
    Delete a knowledge-base document.

    Deletes:
        - original file
        - RAG chunks
        - embeddings

    Only administrators can delete documents.
    """

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=("Only administrators can delete knowledge-base documents."),
        )

    result = await db.execute(select(Document).where(Document.id == document_id))

    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge-base document not found.",
        )

    try:
        # Explicit deletion keeps the behavior clear even
        # though the relationship also has delete-orphan.
        await db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
        )

        await db.delete(document)

        await db.commit()

    except SQLAlchemyError as exc:
        await db.rollback()

        logger.exception(
            "Knowledge-base deletion failed document_id=%s",
            document_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=("Unable to delete the knowledge-base document."),
        ) from exc

    try:
        await FusionRetrievalService.invalidate_cache(
            reason="knowledge_document_deleted"
        )
    except (RuntimeError, TypeError, ValueError, AttributeError):
        logger.exception(
            "RAG cache invalidation failed after document deletion document_id=%s",
            document_id,
        )

    return {
        "message": ("Knowledge-base document deleted successfully."),
        "document_id": str(document_id),
    }
