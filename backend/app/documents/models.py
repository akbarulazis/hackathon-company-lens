"""Document database models.

Defines Document and TextChunk tables. TextChunk uses pgvector
for storing 1536-dimensional embeddings.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Document(Base):
    """Uploaded document associated with a company."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_profiles.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    key_points: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    company: Mapped["CompanyProfile"] = relationship(back_populates="documents")  # noqa: F821
    user: Mapped["User"] = relationship()  # noqa: F821
    text_chunks: Mapped[list["TextChunk"]] = relationship(back_populates="document")

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename!r}, status={self.status!r})>"


class TextChunk(Base):
    """Chunked text with pgvector embedding for semantic search."""

    __tablename__ = "text_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_profiles.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    workspace_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    company: Mapped["CompanyProfile"] = relationship(  # noqa: F821
        back_populates="text_chunks"
    )
    document: Mapped["Document | None"] = relationship(back_populates="text_chunks")

    def __repr__(self) -> str:
        return (
            f"<TextChunk(id={self.id}, company_id={self.company_id}, "
            f"source_type={self.source_type!r}, chunk_index={self.chunk_index})>"
        )
