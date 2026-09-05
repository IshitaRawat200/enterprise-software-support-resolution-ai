from app.rag.embeddings import (
    RAGEmbeddingService,
)


def main() -> None:

    service = RAGEmbeddingService()

    text = (
        "API authentication requires a valid "
        "API key."
    )

    embedding = service.embed_document(
        text
    )

    print(
        f"Embedding dimension: {len(embedding)}"
    )

    print(
        f"Expected dimension: "
        f"{service.EMBEDDING_DIMENSION}"
    )

    if len(embedding) != 1536:
        raise RuntimeError(
            "Embedding dimension mismatch."
        )

    print(
        "Embedding test passed."
    )


if __name__ == "__main__":
    main()