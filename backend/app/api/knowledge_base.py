from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db_session
from app.database.models.knowledge import Document
from app.database.models.user import User
from app.guardrails.auth import get_current_user
from app.guardrails.rbac import require_admin
from app.rag.services.db_rag_ingestion_service import DBRAGIngestionService

router = APIRouter(
    prefix="/knowledge-base",
    tags=["Knowledge Base"],
)


# ============================================================
# CONFIGURATION
# ============================================================

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


# ============================================================
# HELPERS
# ============================================================


def validate_file(file: UploadFile) -> str:
    """
    Validate an uploaded knowledge-base document.
    """

    filename = (file.filename or "").strip()

    if not filename:
        raise HTTPException(
            status_code=400,
            detail="A file name is required.",
        )

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{extension}'. "
                f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            ),
        )

    if file.content_type:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported content type '{file.content_type}'."
                ),
            )

    return extension


def document_to_response(document: Document) -> dict[str, Any]:
    """
    Convert a Document ORM object into a customer-safe response.
    """

    metadata = getattr(document, "metadata_", None)

    if metadata is None:
        metadata = getattr(document, "metadata", None)

    if not isinstance(metadata, dict):
        metadata = {}

    return {
        "id": str(document.id),
        "document_name": document.document_name,
        "document_type": document.document_type,
        "source_url": document.source_url,
        "product_name": document.product_name,
        "product_version": document.product_version,
        "version": document.version,
        "created_at": (
            document.created_at.isoformat()
            if document.created_at
            else None
        ),
        "metadata": metadata,
    }


# ============================================================
# CUSTOMER KNOWLEDGE BASE
# ============================================================


@router.get("/documents")
async def list_knowledge_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """
    Return customer-visible knowledge-base documents.

    This endpoint is intentionally read-only for customers.

    Documents are filtered using metadata.customer_visible when
    that flag is present.

    If customer_visible is not present, the document remains
    visible because existing ERIS documentation was ingested
    before this metadata flag was introduced.
    """

    try:
        result = await db.execute(
            select(Document).order_by(
                Document.created_at.desc()
            )
        )

        documents = list(result.scalars().all())

        response: list[dict[str, Any]] = []

        for document in documents:
            metadata = getattr(document, "metadata_", None)

            if metadata is None:
                metadata = getattr(document, "metadata", None)

            if not isinstance(metadata, dict):
                metadata = {}

            customer_visible = metadata.get(
                "customer_visible",
                True,
            )

            if customer_visible is False:
                continue

            response.append(
                document_to_response(document)
            )

        return response

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to load knowledge-base documents.",
        ) from exc


# ============================================================
# ADMIN DOCUMENT UPLOAD
# ============================================================


@router.post("/documents")
async def upload_knowledge_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Upload and ingest a knowledge-base document.

    Only administrators may upload documents.
    """

    require_admin(current_user)

    extension = validate_file(file)

    temporary_path: Path | None = None

    try:
        suffix = extension

        with NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temporary_file:
            temporary_path = Path(
                temporary_file.name
            )

            shutil.copyfileobj(
                file.file,
                temporary_file,
            )

        file_bytes = temporary_path.read_bytes()

        if not file_bytes:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty.",
            )

        content_hash = hashlib.sha256(
            file_bytes
        ).hexdigest()

        filename = (
            file.filename
            or temporary_path.name
        )

        existing_result = await db.execute(
            select(Document).where(
                Document.content_hash == content_hash
            )
        )

        existing_document = (
            existing_result.scalars().first()
        )

        if existing_document:
            return {
                "message": "Document already exists.",
                "document": document_to_response(
                    existing_document
                ),
                "duplicate": True,
            }

        document = Document(
            document_name=filename,
            document_type=(
                file.content_type
                or extension.lstrip(".")
            ),
            source_url=None,
            product_name=None,
            product_version=None,
            version=None,
            content_hash=content_hash,
            metadata_={
                "customer_visible": True,
                "original_filename": filename,
                "content_type": file.content_type,
            },
        )

        db.add(document)

        await db.flush()

        ingestion_service = DBRAGIngestionService(
            db
        )

        await ingestion_service.ingest_file(
            file_path=str(temporary_path),
            document_id=document.id,
        )

        await db.commit()

        await db.refresh(document)

        return {
            "message": "Knowledge-base document uploaded successfully.",
            "document": document_to_response(
                document
            ),
            "duplicate": False,
        }

    except HTTPException:
        await db.rollback()
        raise

    except Exception as exc:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Knowledge-base document ingestion failed."
            ),
        ) from exc

    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)

        await file.close()


# ============================================================
# ADMIN DELETE
# ============================================================


@router.delete("/documents/{document_id}")
async def delete_knowledge_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Delete a knowledge-base document.

    Only administrators may delete documents.
    """

    require_admin(current_user)

    result = await db.execute(
        select(Document).where(
            Document.id == document_id
        )
    )

    document = result.scalars().first()

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Knowledge-base document not found.",
        )

    try:
        await db.delete(document)
        await db.commit()

        return {
            "message": "Knowledge-base document deleted successfully.",
            "document_id": document_id,
        }

    except SQLAlchemyError as exc:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to delete knowledge-base document.",
        ) from exc