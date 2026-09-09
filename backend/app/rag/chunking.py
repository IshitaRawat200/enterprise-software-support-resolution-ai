from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
)


class DocumentChunker:
    """
    Splits loaded documents into smaller chunks
    suitable for embedding and retrieval.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> None:

        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero.")

        if chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative.")

        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size.")

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n",
                "\n",
                ". ",
                " ",
                "",
            ],
            length_function=len,
            is_separator_regex=False,
        )

    def split_documents(
        self,
        documents: list[Document],
    ) -> list[Document]:

        if not documents:
            return []

        chunks = self._splitter.split_documents(documents)

        processed_chunks: list[Document] = []

        for index, chunk in enumerate(chunks):
            content = chunk.page_content.strip()

            if not content:
                continue

            metadata = {
                **chunk.metadata,
                "chunk_index": index,
            }

            processed_chunks.append(
                Document(
                    page_content=content,
                    metadata=metadata,
                )
            )

        return processed_chunks
