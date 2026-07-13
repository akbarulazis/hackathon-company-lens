"""Document upload validation and processing service.

Handles PDF validation (size, page count, valid PDF), text extraction
using pypdf, LLM key points generation, text chunking with embeddings,
and triggers company re-scoring after processing completes.

Status transitions: pending → processing → ready/failed
"""

import logging
from io import BytesIO

from fastapi import UploadFile
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chatbot.embeddings import chunk_text, generate_embeddings, store_chunks
from app.config import Settings
from app.documents.models import Document
from app.llm.client import LLMClient, LLMClientError

logger = logging.getLogger(__name__)

# Constraints
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_PAGE_COUNT = 200


class DocumentError(Exception):
    """Base exception for document service errors."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


async def upload(
    session: AsyncSession,
    company_id: int,
    user_id: int,
    file: UploadFile,
) -> Document:
    """Validate and create a pending document record.

    Validates that the uploaded file is a valid PDF within size and page
    count limits. Creates a Document record with status='pending'.

    Args:
        session: Async database session.
        company_id: ID of the company this document belongs to.
        user_id: ID of the user uploading the document.
        file: The uploaded file (FastAPI UploadFile).

    Returns:
        The created Document instance with status='pending'.

    Raises:
        DocumentError: If validation fails (not a PDF, too large, too many pages).
    """
    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise DocumentError(
            f"File size exceeds maximum of 20 MB (got {len(content) / (1024 * 1024):.1f} MB).",
            status_code=400,
        )

    # Validate it's a valid PDF and count pages
    try:
        reader = PdfReader(BytesIO(content))
        page_count = len(reader.pages)
    except (PdfReadError, Exception) as e:
        raise DocumentError(
            f"File is not a valid PDF: {e}",
            status_code=400,
        )

    # Validate page count
    if page_count > MAX_PAGE_COUNT:
        raise DocumentError(
            f"PDF exceeds maximum of {MAX_PAGE_COUNT} pages (got {page_count}).",
            status_code=400,
        )

    # Create document record with pending status
    document = Document(
        company_id=company_id,
        user_id=user_id,
        filename=file.filename or "untitled.pdf",
        status="pending",
        page_count=page_count,
    )
    session.add(document)
    await session.flush()

    return document


async def process_document(
    session: AsyncSession,
    document_id: int,
    settings: Settings,
) -> Document:
    """Process a pending document: extract text, generate key points, chunk and embed.

    Delegates to process_document_with_text. This entry point is for cases where
    the PDF content is not available (e.g., stored on object storage). Currently
    not used directly — the worker calls process_document_with_text.

    Args:
        session: Async database session.
        document_id: ID of the document to process.
        settings: Application settings.

    Returns:
        The updated Document instance.

    Raises:
        DocumentError: If document not found.
    """
    # Load document
    stmt = select(Document).where(Document.id == document_id)
    result = await session.execute(stmt)
    document = result.scalar_one_or_none()

    if document is None:
        raise DocumentError(f"Document not found: id={document_id}", status_code=404)

    # In production, retrieve PDF from object storage and extract text
    # For now, this function requires external text input via process_document_with_text
    raise DocumentError(
        "process_document requires stored PDF content. Use process_document_with_text "
        "with pre-extracted text, or implement object storage retrieval.",
        status_code=501,
    )


async def process_document_with_text(
    session: AsyncSession,
    document_id: int,
    text_content: str,
    settings: Settings,
) -> Document:
    """Process a document with pre-extracted text content.

    This is the main processing function called by the worker after
    text extraction. Generates key points, chunks text, creates
    embeddings, and stores everything.

    Args:
        session: Async database session.
        document_id: ID of the document to process.
        text_content: The extracted text from the PDF.
        settings: Application settings.

    Returns:
        The updated Document instance with status='ready'.

    Raises:
        DocumentError: If document not found or processing fails.
    """
    # Load document
    stmt = select(Document).where(Document.id == document_id)
    result = await session.execute(stmt)
    document = result.scalar_one_or_none()

    if document is None:
        raise DocumentError(f"Document not found: id={document_id}", status_code=404)

    # Transition to processing
    document.status = "processing"
    await session.flush()

    try:
        # Validate extracted text
        if not text_content or not text_content.strip():
            raise DocumentError(
                "PDF contains no extractable text.",
                status_code=400,
            )

        # Generate LLM key points summary
        llm_client = LLMClient(settings)
        key_points = await _generate_key_points(llm_client, text_content)

        # Chunk text and generate embeddings
        chunks = chunk_text(text_content, chunk_size=1000, overlap=200)
        embeddings = await generate_embeddings(chunks, settings)

        # Store chunks with embeddings
        stored_chunks = await store_chunks(
            session=session,
            company_id=document.company_id,
            texts=chunks,
            embeddings=embeddings,
            source_type="document",
            document_id=document.id,
        )

        # Update document metadata
        document.key_points = key_points
        document.chunk_count = len(stored_chunks)
        document.status = "ready"
        await session.flush()

        logger.info(
            "Document processed: id=%d, chunks=%d, company_id=%d",
            document.id,
            len(stored_chunks),
            document.company_id,
        )

        return document

    except DocumentError:
        document.status = "failed"
        await session.flush()
        raise
    except LLMClientError as e:
        logger.error("LLM error processing document %d: %s", document_id, e)
        document.status = "failed"
        await session.flush()
        raise DocumentError(f"LLM processing failed: {e}", status_code=500)
    except Exception as e:
        logger.exception("Unexpected error processing document %d: %s", document_id, e)
        document.status = "failed"
        await session.flush()
        raise


def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF file bytes using pypdf.

    Args:
        content: Raw PDF file bytes.

    Returns:
        Concatenated text from all pages.

    Raises:
        DocumentError: If the PDF is invalid or contains no text.
    """
    try:
        reader = PdfReader(BytesIO(content))
        pages_text: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
        return "\n".join(pages_text)
    except (PdfReadError, Exception) as e:
        raise DocumentError(f"Failed to extract text from PDF: {e}", status_code=400)


async def _generate_key_points(llm_client: LLMClient, text_content: str) -> str:
    """Generate a key points summary of the document content using LLM.

    Args:
        llm_client: The LLM client instance.
        text_content: The extracted document text.

    Returns:
        A string containing the key points summary.
    """
    # Truncate very long texts to fit within context window
    max_chars = 40000
    truncated_text = text_content[:max_chars] if len(text_content) > max_chars else text_content

    system_prompt = (
        "You are a document analysis assistant. Extract and summarize the key points "
        "from the provided document text. Focus on the most important facts, findings, "
        "and insights. Return a concise bullet-point summary."
    )
    prompt = f"Extract key points from this document:\n\n{truncated_text}"

    return await llm_client.generate(prompt=prompt, system_prompt=system_prompt)
