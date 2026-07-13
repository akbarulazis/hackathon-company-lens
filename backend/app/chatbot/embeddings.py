"""Embedding generation and vector search utilities.

Provides text chunking, OpenAI embedding generation, storage of
TextChunk records with embeddings, and workspace-scoped vector
similarity search using pgvector cosine distance.
"""

import logging
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.documents.models import TextChunk
from app.workspaces.models import WorkspaceCompany

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-ada-002"
EMBEDDING_DIMENSIONS = 1536


def chunk_text(text_content: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into chunks of approximately chunk_size characters with overlap.

    Splits at word boundaries to avoid cutting words in half. The concatenation
    of all chunks (accounting for overlap) reconstructs the original text.

    Args:
        text_content: The text to split into chunks.
        chunk_size: Target size for each chunk in characters (~1000).
        overlap: Number of characters to overlap between consecutive chunks (~200).

    Returns:
        List of text chunks. Returns a single-element list with the original
        text if it's shorter than chunk_size, or an empty list if text is empty.
    """
    if not text_content:
        return []

    if len(text_content) <= chunk_size:
        return [text_content]

    chunks: list[str] = []
    start = 0

    while start < len(text_content):
        # Determine end position for this chunk
        end = start + chunk_size

        if end >= len(text_content):
            # Last chunk: take everything remaining
            chunks.append(text_content[start:])
            break

        # Find a word boundary near the end position
        # Look backwards from end to find a space
        boundary = end
        while boundary > start and text_content[boundary] != " ":
            boundary -= 1

        # If no space found (very long word), just cut at chunk_size
        if boundary == start:
            boundary = end

        chunks.append(text_content[start:boundary])

        # Calculate next start position with overlap
        # Move back 'overlap' chars from the boundary, then find a word boundary
        next_start = boundary - overlap

        # Ensure we don't go backwards past current start
        if next_start <= start:
            next_start = boundary
        else:
            # For text with no spaces (single long word), just use the calculated position
            if next_start < len(text_content) and text_content[next_start] == " ":
                # Already at a space, move past it
                next_start += 1
            elif next_start < len(text_content):
                # Snap to a word boundary: look backwards for a space
                snap = next_start
                while snap > start and snap < len(text_content) and text_content[snap] != " ":
                    snap -= 1
                if snap > start and snap < len(text_content) and text_content[snap] == " ":
                    next_start = snap + 1
                # If no space found, keep next_start as-is (will split mid-word)

            # Final safety check: ensure forward progress
            if next_start <= start:
                next_start = boundary

        start = next_start

    return chunks


async def generate_embeddings(
    texts: list[str], settings: Settings
) -> list[list[float]]:
    """Generate embeddings for a batch of texts using OpenAI text-embedding-ada-002.

    Args:
        texts: List of text strings to embed.
        settings: Application settings containing OPENAI_API_KEY.

    Returns:
        List of 1536-dimensional embedding vectors, one per input text.

    Raises:
        Exception: If the OpenAI API call fails.
    """
    if not texts:
        return []

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )

    # Sort by index to ensure ordering matches input
    sorted_embeddings = sorted(response.data, key=lambda x: x.index)
    return [item.embedding for item in sorted_embeddings]


async def store_chunks(
    session: AsyncSession,
    company_id: int,
    texts: list[str],
    embeddings: list[list[float]],
    source_type: str,
    document_id: Optional[int] = None,
    workspace_id: Optional[int] = None,
) -> list[TextChunk]:
    """Persist TextChunk records with embeddings to the database.

    Args:
        session: Async SQLAlchemy session.
        company_id: ID of the company these chunks belong to.
        texts: List of text content for each chunk.
        embeddings: List of embedding vectors corresponding to texts.
        source_type: Type of source ("research" or "document").
        document_id: Optional document ID if chunks are from a document.
        workspace_id: Optional workspace ID for scoping.

    Returns:
        List of created TextChunk instances.
    """
    if not texts or not embeddings:
        return []

    chunks: list[TextChunk] = []
    for idx, (content, embedding) in enumerate(zip(texts, embeddings)):
        chunk = TextChunk(
            company_id=company_id,
            document_id=document_id,
            workspace_id=workspace_id,
            content=content,
            embedding=embedding,
            source_type=source_type,
            chunk_index=idx,
        )
        session.add(chunk)
        chunks.append(chunk)

    await session.flush()
    return chunks


async def search_similar_chunks(
    session: AsyncSession,
    query_embedding: list[float],
    workspace_id: int,
    top_k: int = 5,
    threshold: float = 0.5,
) -> list[TextChunk]:
    """Perform pgvector cosine similarity search scoped to a workspace.

    Workspace scoping: joins TextChunk with WorkspaceCompany on company_id,
    filtered by workspace_id.

    Threshold logic:
    1. First query: get top_k chunks with cosine similarity > threshold
    2. If fewer than 3 results: get top 3 regardless of threshold
    3. Return results ordered by similarity descending

    Args:
        session: Async SQLAlchemy session.
        query_embedding: The query embedding vector (1536-dim).
        workspace_id: ID of the workspace to scope the search to.
        top_k: Maximum number of results to return (default 5).
        threshold: Minimum cosine similarity threshold (default 0.5).

    Returns:
        List of TextChunk objects ordered by cosine similarity descending.
    """
    # pgvector cosine distance: 1 - cosine_similarity
    # So similarity > threshold means distance < (1 - threshold)
    distance_threshold = 1.0 - threshold

    # First: try to get top_k chunks above threshold
    stmt = (
        select(TextChunk)
        .join(
            WorkspaceCompany,
            TextChunk.company_id == WorkspaceCompany.company_id,
        )
        .where(WorkspaceCompany.workspace_id == workspace_id)
        .where(TextChunk.embedding.isnot(None))
        .where(
            TextChunk.embedding.cosine_distance(query_embedding) < distance_threshold
        )
        .order_by(TextChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )

    result = await session.execute(stmt)
    chunks = list(result.scalars().all())

    # If fewer than 3 above threshold, get top 3 regardless
    if len(chunks) < 3:
        stmt_fallback = (
            select(TextChunk)
            .join(
                WorkspaceCompany,
                TextChunk.company_id == WorkspaceCompany.company_id,
            )
            .where(WorkspaceCompany.workspace_id == workspace_id)
            .where(TextChunk.embedding.isnot(None))
            .order_by(TextChunk.embedding.cosine_distance(query_embedding))
            .limit(3)
        )

        result_fallback = await session.execute(stmt_fallback)
        chunks = list(result_fallback.scalars().all())

    return chunks
