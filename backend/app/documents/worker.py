"""ARQ job function for document processing.

Defines `process_document` job function that is executed by the ARQ worker.
Extracts text from a stored PDF, delegates to the document service for
LLM summarization and embedding generation, triggers company re-scoring,
and pushes WebSocket status events throughout.

Timeout: 120s, max 2 attempts (configured in jobs/settings.py).
"""

import logging

from app.config import get_settings
from app.database import create_session_factory
from app.documents.service import (
    DocumentError,
    extract_text_from_pdf,
    process_document_with_text,
)
from app.jobs.registry import (
    enqueue_job,
    mark_job_completed,
    mark_job_failed,
    mark_job_running,
)
from app.notifications.events import DocumentStatusEvent
from app.notifications.manager import get_notification_manager

logger = logging.getLogger(__name__)


async def process_document(
    ctx: dict,
    document_id: int,
    user_id: int,
    company_id: int,
    pdf_content: bytes,
) -> None:
    """ARQ job function: process an uploaded PDF document.

    Steps:
    1. Mark job as running
    2. Push 'processing' status via WebSocket
    3. Extract text from PDF
    4. Invoke service to generate key points, chunk, and embed
    5. Trigger company re-scoring via score_profile job
    6. Push 'ready' status via WebSocket
    7. Mark job completed

    On failure: set document status to 'failed', push failure event,
    mark job failed.

    Args:
        ctx: ARQ worker context dict (contains redis connection).
        document_id: ID of the Document record to process.
        user_id: ID of the user who uploaded the document.
        company_id: ID of the company the document belongs to.
        pdf_content: Raw bytes of the PDF file.
    """
    redis = ctx.get("redis")
    job_type = "process_document"
    resource_id = str(document_id)

    logger.info(
        "Starting process_document job: document_id=%d, company_id=%d, user_id=%d",
        document_id,
        company_id,
        user_id,
    )

    # Mark job as running in dedup registry
    if redis:
        await mark_job_running(redis, job_type, resource_id)

    settings = get_settings()
    session_factory = create_session_factory(settings)

    # Push processing status event
    await _publish_status(user_id, document_id, company_id, "processing", "Document processing started")

    async with session_factory() as session:
        try:
            # Step 1: Extract text from PDF
            text_content = extract_text_from_pdf(pdf_content)

            if not text_content or not text_content.strip():
                raise DocumentError(
                    "PDF contains no extractable text.",
                    status_code=400,
                )

            # Step 2: Process document (key points, chunking, embeddings)
            document = await process_document_with_text(
                session=session,
                document_id=document_id,
                text_content=text_content,
                settings=settings,
            )
            await session.commit()

            # Step 3: Trigger company re-scoring
            await _trigger_rescoring(redis, company_id, user_id)

            # Step 4: Push ready status event
            await _publish_status(
                user_id, document_id, company_id, "ready", "Document processed successfully"
            )

            # Mark job completed in dedup registry
            if redis:
                await mark_job_completed(redis, job_type, resource_id)

            logger.info(
                "process_document completed: document_id=%d, chunks=%d",
                document_id,
                document.chunk_count or 0,
            )

        except DocumentError as e:
            logger.error(
                "process_document failed (DocumentError): document_id=%d, error=%s",
                document_id,
                e.detail,
            )

            # Ensure status is set to failed in the DB
            from sqlalchemy import select

            from app.documents.models import Document

            stmt = select(Document).where(Document.id == document_id)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()
            if doc and doc.status != "failed":
                doc.status = "failed"
            await session.commit()

            # Push failure event
            await _publish_status(
                user_id, document_id, company_id, "failed", e.detail
            )

            # Mark job failed in dedup registry
            if redis:
                await mark_job_failed(redis, job_type, resource_id)

            raise

        except Exception as e:
            logger.exception(
                "process_document failed: document_id=%d, error=%s", document_id, e
            )

            # Set status to failed
            from sqlalchemy import select

            from app.documents.models import Document

            stmt = select(Document).where(Document.id == document_id)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()
            if doc and doc.status != "failed":
                doc.status = "failed"
            await session.commit()

            # Push failure event
            await _publish_status(
                user_id,
                document_id,
                company_id,
                "failed",
                f"Document processing failed: {e}",
            )

            # Mark job failed in dedup registry
            if redis:
                await mark_job_failed(redis, job_type, resource_id)

            raise


async def _publish_status(
    user_id: int,
    document_id: int,
    company_id: int,
    status: str,
    message: str,
) -> None:
    """Publish a document status event via WebSocket.

    Silently catches errors — WebSocket failure should not fail the job.
    """
    try:
        manager = get_notification_manager()
        event = DocumentStatusEvent(
            document_id=document_id,
            company_id=company_id,
            status=status,
            message=message,
        )
        await manager.publish(user_id, event)
    except Exception as ws_err:
        logger.warning(
            "Failed to push document status event: document_id=%d, error=%s",
            document_id,
            ws_err,
        )


async def _trigger_rescoring(redis, company_id: int, user_id: int) -> None:
    """Trigger company re-scoring via the score_profile ARQ job.

    Uses the job registry for deduplication — if a scoring job is
    already pending/running for this company, the enqueue is discarded.
    """
    if redis is None:
        logger.warning(
            "Cannot trigger re-scoring: no Redis connection (company_id=%d)",
            company_id,
        )
        return

    try:
        from arq import ArqRedis

        arq_redis = ArqRedis(pool_or_conn=redis.connection_pool)
        await enqueue_job(
            arq_redis=arq_redis,
            redis=redis,
            job_type="score_profile",
            resource_id=str(company_id),
            company_id=company_id,
            user_id=user_id,
        )
        logger.info(
            "Triggered re-scoring for company_id=%d after document processing",
            company_id,
        )
    except Exception as e:
        # Re-scoring failure should not fail document processing
        logger.warning(
            "Failed to trigger re-scoring for company_id=%d: %s", company_id, e
        )
