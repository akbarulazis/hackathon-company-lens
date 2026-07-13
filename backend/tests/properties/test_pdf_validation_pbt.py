"""Property-based tests for PDF validation constraints.

# Feature: company-lens-rebuild
# Property 27: PDF Validation Constraints

Validates: Requirements 12.1
"""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from pypdf import PdfWriter

from app.documents.service import (
    DocumentError,
    MAX_FILE_SIZE_BYTES,
    MAX_PAGE_COUNT,
    upload,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


def make_valid_pdf(num_pages: int) -> bytes:
    """Create a minimal valid PDF with the specified number of pages.

    Uses pypdf PdfWriter to produce actual valid PDF content.
    """
    writer = PdfWriter()
    for i in range(num_pages):
        writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def make_upload_file(content: bytes, filename: str = "test.pdf") -> MagicMock:
    """Create a mock UploadFile that returns the given content on read."""
    file = MagicMock()
    file.filename = filename
    file.read = AsyncMock(return_value=content)
    return file


def make_mock_document(**kwargs):
    """Create a mock Document instance to avoid SQLAlchemy mapper issues."""
    doc = MagicMock()
    doc.company_id = kwargs.get("company_id", 1)
    doc.user_id = kwargs.get("user_id", 1)
    doc.filename = kwargs.get("filename", "test.pdf")
    doc.status = kwargs.get("status", "pending")
    doc.page_count = kwargs.get("page_count", None)
    return doc


# Strategy: valid page counts (1 to 200 inclusive)
valid_page_count_strategy = st.integers(min_value=1, max_value=200)

# Strategy: page counts exceeding the limit (201+)
excess_page_count_strategy = st.integers(min_value=201, max_value=210)

# Strategy: random bytes for non-PDF files
random_bytes_strategy = st.binary(min_size=1, max_size=1024)

# Strategy: text file content
text_content_strategy = st.text(min_size=1, max_size=500).map(lambda s: s.encode("utf-8"))

# Strategy: file sizes exceeding 20 MB (just over the limit)
# We generate a small amount over to avoid memory issues in testing
excess_size_bytes_strategy = st.integers(
    min_value=MAX_FILE_SIZE_BYTES + 1,
    max_value=MAX_FILE_SIZE_BYTES + 1024,
)


# ===========================================================================
# Property 27: PDF Validation Constraints
# ===========================================================================


@given(page_count=valid_page_count_strategy)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property27_valid_pdf_within_limits_accepted(page_count: int) -> None:
    """Property 27: For any valid PDF file ≤20 MB with ≤200 pages,
    upload SHALL accept the file (no DocumentError raised).

    **Validates: Requirements 12.1**
    """
    pdf_content = make_valid_pdf(page_count)

    # Ensure the generated PDF is within size limits
    assume(len(pdf_content) <= MAX_FILE_SIZE_BYTES)

    file = make_upload_file(pdf_content)
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    mock_doc = make_mock_document(
        company_id=1, user_id=1, page_count=page_count, status="pending"
    )

    with patch("app.documents.service.Document", return_value=mock_doc):
        # Should not raise DocumentError
        result = await upload(
            session=session,
            company_id=1,
            user_id=1,
            file=file,
        )

    # Document should be created with pending status
    assert result is not None
    assert result.status == "pending"
    assert result.page_count == page_count
    assert result.company_id == 1
    assert result.user_id == 1


@given(excess_bytes=excess_size_bytes_strategy)
@settings(max_examples=20)
@pytest.mark.asyncio
async def test_property27_file_exceeding_20mb_rejected(excess_bytes: int) -> None:
    """Property 27: For any file exceeding 20 MB, upload SHALL raise
    DocumentError mentioning size.

    **Validates: Requirements 12.1**
    """
    # Create content that exceeds the max size
    # Use a valid PDF header + padding to exceed size
    content = b"%PDF-1.4" + b"\x00" * (excess_bytes - 8)

    file = make_upload_file(content)
    session = AsyncMock()

    with pytest.raises(DocumentError) as exc_info:
        await upload(session=session, company_id=1, user_id=1, file=file)

    # Error message should mention size
    assert "size" in exc_info.value.detail.lower() or "20 MB" in exc_info.value.detail


@given(page_count=excess_page_count_strategy)
@settings(max_examples=10)
@pytest.mark.asyncio
async def test_property27_pdf_exceeding_200_pages_rejected(page_count: int) -> None:
    """Property 27: For any PDF with >200 pages, upload SHALL raise
    DocumentError mentioning page count.

    **Validates: Requirements 12.1**
    """
    pdf_content = make_valid_pdf(page_count)

    # Ensure the PDF is within size limits (so size check doesn't trigger first)
    assume(len(pdf_content) <= MAX_FILE_SIZE_BYTES)

    file = make_upload_file(pdf_content)
    session = AsyncMock()

    with pytest.raises(DocumentError) as exc_info:
        await upload(session=session, company_id=1, user_id=1, file=file)

    # Error message should mention pages
    assert "page" in exc_info.value.detail.lower()
    assert str(MAX_PAGE_COUNT) in exc_info.value.detail


@given(data=random_bytes_strategy)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property27_non_pdf_random_bytes_rejected(data: bytes) -> None:
    """Property 27: For any non-PDF file (random bytes), upload SHALL raise
    DocumentError indicating the file is not a valid PDF.

    **Validates: Requirements 12.1**
    """
    # Filter out content that accidentally starts with %PDF (valid PDF header)
    assume(not data.startswith(b"%PDF"))
    # Also filter out content that exceeds size limit (to test PDF check, not size check)
    assume(len(data) <= MAX_FILE_SIZE_BYTES)

    file = make_upload_file(data, filename="random.bin")
    session = AsyncMock()

    with pytest.raises(DocumentError) as exc_info:
        await upload(session=session, company_id=1, user_id=1, file=file)

    # Error should indicate it's not a valid PDF
    assert "not a valid PDF" in exc_info.value.detail or "PDF" in exc_info.value.detail


@given(text_data=text_content_strategy)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property27_non_pdf_text_file_rejected(text_data: bytes) -> None:
    """Property 27: For any text file (not a PDF), upload SHALL raise
    DocumentError indicating the file is not a valid PDF.

    **Validates: Requirements 12.1**
    """
    # Ensure text doesn't accidentally look like a PDF
    assume(not text_data.startswith(b"%PDF"))
    assume(len(text_data) <= MAX_FILE_SIZE_BYTES)

    file = make_upload_file(text_data, filename="document.txt")
    session = AsyncMock()

    with pytest.raises(DocumentError) as exc_info:
        await upload(session=session, company_id=1, user_id=1, file=file)

    assert "not a valid PDF" in exc_info.value.detail or "PDF" in exc_info.value.detail


@given(page_count=st.just(200))
@settings(max_examples=5)
@pytest.mark.asyncio
async def test_property27_boundary_exactly_200_pages_accepted(page_count: int) -> None:
    """Property 27: A PDF with exactly 200 pages (the boundary) SHALL be accepted.

    **Validates: Requirements 12.1**
    """
    pdf_content = make_valid_pdf(page_count)
    assume(len(pdf_content) <= MAX_FILE_SIZE_BYTES)

    file = make_upload_file(pdf_content)
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    mock_doc = make_mock_document(
        company_id=1, user_id=1, page_count=200, status="pending"
    )

    with patch("app.documents.service.Document", return_value=mock_doc):
        result = await upload(session=session, company_id=1, user_id=1, file=file)

    assert result is not None
    assert result.status == "pending"
    assert result.page_count == 200


@given(page_count=st.just(201))
@settings(max_examples=5)
@pytest.mark.asyncio
async def test_property27_boundary_201_pages_rejected(page_count: int) -> None:
    """Property 27: A PDF with exactly 201 pages (one over limit) SHALL be rejected.

    **Validates: Requirements 12.1**
    """
    pdf_content = make_valid_pdf(page_count)
    assume(len(pdf_content) <= MAX_FILE_SIZE_BYTES)

    file = make_upload_file(pdf_content)
    session = AsyncMock()

    with pytest.raises(DocumentError) as exc_info:
        await upload(session=session, company_id=1, user_id=1, file=file)

    assert "page" in exc_info.value.detail.lower()
    assert str(MAX_PAGE_COUNT) in exc_info.value.detail
