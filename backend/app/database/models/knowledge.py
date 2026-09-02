from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from .user import User
    from .ticket import SupportTicket


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    article_code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
    )

    product_name: Mapped[str | None] = mapped_column(
        String(255),
    )

    product_version: Mapped[str | None] = mapped_column(
        String(100),
    )

    source_url: Mapped[str | None] = mapped_column(
        Text,
    )

    version: Mapped[str | None] = mapped_column(
        String(100),
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="knowledge_article",
        cascade="all, delete-orphan",
    )

    article_usage: Mapped[list["KnowledgeArticleUsage"]] = relationship(
        "KnowledgeArticleUsage",
        back_populates="article",
        cascade="all, delete-orphan",
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    knowledge_article_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_articles.id", ondelete="SET NULL"),
    )

    document_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    document_type: Mapped[str | None] = mapped_column(
        String(100),
    )

    source_url: Mapped[str | None] = mapped_column(
        Text,
    )

    product_name: Mapped[str | None] = mapped_column(
        String(255),
    )

    product_version: Mapped[str | None] = mapped_column(
        String(100),
    )

    version: Mapped[str | None] = mapped_column(
        String(100),
    )

    content_hash: Mapped[str | None] = mapped_column(
        String(128),
    )

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    knowledge_article: Mapped["KnowledgeArticle | None"] = relationship(
        "KnowledgeArticle",
        back_populates="documents",
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    token_count: Mapped[int | None] = mapped_column(
        Integer,
    )

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536),
    )

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks",
    )


class KnowledgeArticleUsage(Base):
    __tablename__ = "knowlege_article_usage"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    article_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_articles.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    ticket_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("support_tickets.id", ondelete="SET NULL"),
    )

    query: Mapped[str | None] = mapped_column(
        Text,
    )

    usage_type: Mapped[str | None] = mapped_column(
        String(100),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    article: Mapped["KnowledgeArticle"] = relationship(
        "KnowledgeArticle",
        back_populates="article_usage",
    )

    ticket: Mapped["SupportTicket | None"] = relationship(
        "SupportTicket",
        back_populates="article_usage",
    )