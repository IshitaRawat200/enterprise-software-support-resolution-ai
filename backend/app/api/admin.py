# from __future__ import annotations

# import os
# import tempfile
# from pathlib import Path
# from uuid import UUID

# from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
# from sqlalchemy import desc, select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.database.models.knowledge import Document
# from app.database.models.evaluation import EvaluationRun
# from app.database.session import get_db

# router = APIRouter(
#     prefix="/admin",
#     tags=["Admin"],
# )


# # ---------------------------------------------------------------------------
# # Knowledge Documents
# # ---------------------------------------------------------------------------


# @router.get("/knowledge/documents")
# async def list_knowledge_documents(
#     db: AsyncSession = Depends(get_db),
# ):
#     result = await db.execute(
#         select(Document).order_by(desc(Document.created_at))
#     )

#     documents = result.scalars().all()

#     return [
#         {
#             "id": str(document.id),
#             "document_name": document.document_name,
#             "document_type": document.document_type,
#             "product_name": document.product_name,
#             "product_version": document.product_version,
#             "version": document.version,
#             "source_url": document.source_url,
#             "created_at": document.created_at.isoformat(),
#         }
#         for document in documents
#     ]


# @router.post(
#     "/knowledge/documents",
#     status_code=status.HTTP_201_CREATED,
# )
# async def upload_knowledge_document(
#     file: UploadFile = File(...),
#     db: AsyncSession = Depends(get_db),
# ):
#     if not file.filename:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="A file is required.",
#         )

#     filename = Path(file.filename).name

#     if not filename.lower().endswith(".pdf"):
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Only PDF documents are allowed.",
#         )

#     content = await file.read()

#     if not content:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="The uploaded PDF is empty.",
#         )

#     # Temporary storage for the ingestion pipeline.
#     temp_path: str | None = None

#     try:
#         with tempfile.NamedTemporaryFile(
#             suffix=".pdf",
#             delete=False,
#         ) as temp_file:
#             temp_file.write(content)
#             temp_path = temp_file.name

#         # ------------------------------------------------------------------
#         # TODO:
#         # Connect the existing RAG PDF ingestion/chunking/embedding service
#         # here.
#         #
#         # The ingestion service should:
#         #   1. Extract PDF text
#         #   2. Create the documents row
#         #   3. Create document_chunks
#         #   4. Generate 1536-dimensional embeddings
#         #   5. Store embeddings in Supabase
#         #   6. Invalidate the RAG cache
#         #
#         # We will wire this to your existing RAG implementation next.
#         # ------------------------------------------------------------------

#         document = Document(
#             document_name=filename,
#             document_type="pdf",
#         )

#         db.add(document)
#         await db.commit()
#         await db.refresh(document)

#         return {
#             "id": str(document.id),
#             "document_name": document.document_name,
#             "document_type": document.document_type,
#             "product_name": document.product_name,
#             "product_version": document.product_version,
#             "version": document.version,
#             "source_url": document.source_url,
#             "created_at": document.created_at.isoformat(),
#         }

#     finally:
#         if temp_path and os.path.exists(temp_path):
#             os.remove(temp_path)


# @router.delete("/knowledge/documents/{document_id}")
# async def delete_knowledge_document(
#     document_id: UUID,
#     db: AsyncSession = Depends(get_db),
# ):
#     result = await db.execute(
#         select(Document).where(Document.id == document_id)
#     )

#     document = result.scalar_one_or_none()

#     if document is None:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Knowledge document not found.",
#         )

#     await db.delete(document)
#     await db.commit()

#     return {
#         "message": "Knowledge document deleted successfully.",
#         "document_id": str(document_id),
#     }


# # ---------------------------------------------------------------------------
# # Evaluation
# # ---------------------------------------------------------------------------


# @router.get("/evaluation/latest")
# async def get_latest_evaluation(
#     db: AsyncSession = Depends(get_db),
# ):
#     result = await db.execute(
#         select(EvaluationRun)
#         .order_by(desc(EvaluationRun.created_at))
#         .limit(1)
#     )

#     evaluation = result.scalar_one_or_none()

#     if evaluation is None:
#         return None

#     report = evaluation.report or {}

#     return {
#         "run_id": str(evaluation.run_id),
#         "created_at": evaluation.created_at.isoformat(),
#         "status": evaluation.status,
#         "total_cases": evaluation.total_cases,

#         "tsr": report.get("tsr"),
#         "p95_latency_ms": report.get("p95_latency_ms"),
#         "sql_correctness": report.get("sql_correctness"),
#         "query_routing_accuracy": report.get(
#             "query_routing_accuracy"
#         ),
#         "risk_classification_accuracy": report.get(
#             "risk_classification_accuracy"
#         ),
#         "escalation_recall": report.get("escalation_recall"),

#         "faithfulness": report.get("faithfulness"),
#         "answer_relevance": report.get("answer_relevance"),
#         "context_precision": report.get("context_precision"),
#         "context_recall": report.get("context_recall"),
#         "llm_judge_score": report.get("llm_judge_score"),
#     }