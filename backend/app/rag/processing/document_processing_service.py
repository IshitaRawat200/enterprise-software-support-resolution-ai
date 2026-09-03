from __future__ import annotations

from langchain_core.documents import Document


class DocumentProcessingService:
    """
    Normalizes documents loaded from different sources.

    Responsibilities:

    1. Clean document text.
    2. Normalize metadata.
    3. Remove empty documents.
    """

    def process(
        self,
        documents: list[Document],
    ) -> list[Document]:

        processed_documents: list[Document] = []

        for document in documents:

            content = document.page_content.strip()

            if not content:
                continue

            metadata = dict(
                document.metadata
            )

            metadata.setdefault(
                "document_name",
                "unknown",
            )

            metadata.setdefault(
                "document_type",
                "unknown",
            )

            processed_documents.append(
                Document(
                    page_content=content,
                    metadata=metadata,
                )
            )

        return processed_documents