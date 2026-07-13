"""Documents API router.

Provides endpoints for uploading PDF documents to a company,
listing a company's documents, and retrieving a single document's
status and metadata. All endpoints require authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.companies.models import CompanyProfile
from app.dependencies import get_db, get_redis
from app.documents.models import Document
from app.documents.schemas import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.documents.service import DocumentError, upload
from app.jobs.registry import enqueue_job

router = APIRouter(prefix="/api/companies", tags=["documents"])


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str


@router.post(
    "/{company_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file"},
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
        404: {"model": ErrorResponse, "description": "Company not found"},
    },
)
async def upload_document(
    company_id: int,
    file: UploadFile,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> DocumentUploadResponse:
    """Upload a PDF document for a company.

    Validates the file is a valid PDF (≤20 MB, ≤200 pages), creates a
    Document record with status='pending', and enqueues a background job
    for processing (text extraction, key points, embeddings).
    """
    # Verify company exists
    company = await _get_company_or_404(session, company_id)

    # Read file content for validation and later processing
    file_content = await file.read()
    # Reset file position for the upload service
    await file.seek(0)

    try:
        document = await upload(session, company_id, current_user.id, file)
        await session.commit()
    except DocumentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    # Enqueue background processing job
    try:
        from arq import ArqRedis

        arq_redis = ArqRedis(pool_or_conn=redis.connection_pool)
        await enqueue_job(
            arq_redis=arq_redis,
            redis=redis,
            job_type="process_document",
            resource_id=str(document.id),
            document_id=document.id,
            user_id=current_user.id,
            company_id=company_id,
            pdf_content=file_content,
        )
    except Exception as e:
        # Job enqueue failure is non-fatal — the document stays in pending state
        # and can be re-processed manually later
        import logging

        logging.getLogger(__name__).warning(
            "Failed to enqueue process_document job: document_id=%d, error=%s",
            document.id,
            e,
        )

    return DocumentUploadResponse(
        id=document.id,
        company_id=document.company_id,
        filename=document.filename,
        status=document.status,
        message=f"Document '{document.filename}' uploaded and queued for processing.",
    )


@router.get(
    "/{company_id}/documents",
    response_model=DocumentListResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
        404: {"model": ErrorResponse, "description": "Company not found"},
    },
)
async def list_documents(
    company_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentListResponse:
    """List all documents for a company.

    Returns documents ordered by creation date descending (newest first).
    """
    # Verify company exists
    await _get_company_or_404(session, company_id)

    stmt = (
        select(Document)
        .where(Document.company_id == company_id)
        .order_by(Document.created_at.desc())
    )
    result = await session.execute(stmt)
    documents = list(result.scalars().all())

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in documents]
    )


@router.get(
    "/{company_id}/documents/{doc_id}",
    response_model=DocumentResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
        404: {"model": ErrorResponse, "description": "Document or company not found"},
    },
)
async def get_document(
    company_id: int,
    doc_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """Get a single document's status and metadata.

    Returns 404 if the company or document does not exist, or if
    the document does not belong to the specified company.
    """
    # Verify company exists
    await _get_company_or_404(session, company_id)

    stmt = select(Document).where(
        Document.id == doc_id,
        Document.company_id == company_id,
    )
    result = await session.execute(stmt)
    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: id={doc_id}",
        )

    return DocumentResponse.model_validate(document)


async def _get_company_or_404(session: AsyncSession, company_id: int) -> CompanyProfile:
    """Load a company by ID or raise 404."""
    stmt = select(CompanyProfile).where(CompanyProfile.id == company_id)
    result = await session.execute(stmt)
    company = result.scalar_one_or_none()

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company not found: id={company_id}",
        )

    return company
