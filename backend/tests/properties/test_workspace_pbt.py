"""Property-based tests for workspace management.

# Feature: company-lens-rebuild
# Property 18: Workspace Name Validation
# Property 19: Workspace Duplicate Name Rejection
# Property 20: Workspace Company Limit Enforcement
# Property 21: Workspace Add/Remove Integrity
# Property 22: Duplicate Company in Workspace Rejection
# Property 23: Multi-Workspace Company Association

Validates: Requirements 9.1, 9.2, 9.3, 9.6, 10.1, 10.2, 10.4, 10.5, 20.1, 20.2, 20.3, 20.4, 20.5
"""

import string
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.workspaces.schemas import WorkspaceCreate, WorkspaceUpdate
from app.workspaces.service import (
    WorkspaceError,
    add_company,
    create_workspace,
    remove_company,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid workspace names: 1-100 characters of printable content
valid_workspace_name_strategy = st.text(
    alphabet=st.sampled_from(string.ascii_letters + string.digits + " _-"),
    min_size=1,
    max_size=100,
)

# Invalid names: too short (empty) or too long (>100 chars)
empty_name_strategy = st.just("")

too_long_name_strategy = st.text(
    alphabet=st.sampled_from(string.ascii_letters + string.digits + " "),
    min_size=101,
    max_size=200,
)

# User IDs
user_id_strategy = st.integers(min_value=1, max_value=100_000)

# Workspace IDs
workspace_id_strategy = st.integers(min_value=1, max_value=100_000)

# Company IDs
company_id_strategy = st.integers(min_value=1, max_value=100_000)

# Company limits (configurable, default 3)
company_limit_strategy = st.integers(min_value=1, max_value=20)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def mock_workspace(workspace_id: int, user_id: int, name: str, company_limit: int = 3):
    """Create a mock workspace object."""
    ws = MagicMock()
    ws.id = workspace_id
    ws.user_id = user_id
    ws.name = name
    ws.company_limit = company_limit
    ws.created_at = datetime.now(timezone.utc)
    ws.updated_at = datetime.now(timezone.utc)
    return ws


def mock_company(company_id: int, status: str = "ready", client_status: str = "prospect"):
    """Create a mock company profile object."""
    company = MagicMock()
    company.id = company_id
    company.name = f"Company {company_id}"
    company.status = MagicMock(value=status)
    company.client_status = MagicMock(value=client_status)
    company.industry = "Technology"
    company.overall_score = 3.5
    return company


# ===========================================================================
# Property 18: Workspace Name Validation
# ===========================================================================


@given(name=valid_workspace_name_strategy)
@settings(max_examples=100)
def test_property18_valid_names_accepted(name: str) -> None:
    """Property 18: For any string between 1 and 100 characters, the
    WorkspaceCreate schema SHALL accept it as a valid name.

    **Validates: Requirements 9.1**
    """
    schema = WorkspaceCreate(name=name)
    assert schema.name == name
    assert 1 <= len(schema.name) <= 100


@given(name=empty_name_strategy)
@settings(max_examples=10)
def test_property18_empty_name_rejected(name: str) -> None:
    """Property 18: An empty string SHALL be rejected by WorkspaceCreate.

    **Validates: Requirements 9.1**
    """
    with pytest.raises(ValidationError):
        WorkspaceCreate(name=name)


@given(name=too_long_name_strategy)
@settings(max_examples=50)
def test_property18_too_long_name_rejected(name: str) -> None:
    """Property 18: Any string with more than 100 characters SHALL be rejected
    by WorkspaceCreate.

    **Validates: Requirements 9.1**
    """
    with pytest.raises(ValidationError):
        WorkspaceCreate(name=name)


@given(
    length=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=50)
def test_property18_boundary_lengths_accepted(length: int) -> None:
    """Property 18: Any name with length in [1, 100] SHALL be accepted.

    **Validates: Requirements 9.1**
    """
    name = "a" * length
    schema = WorkspaceCreate(name=name)
    assert len(schema.name) == length


# ===========================================================================
# Property 19: Workspace Duplicate Name Rejection
# ===========================================================================


@given(
    name=valid_workspace_name_strategy,
    user_id=user_id_strategy,
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property19_duplicate_name_same_user_rejected(
    name: str, user_id: int
) -> None:
    """Property 19: For any user who already owns a workspace with a given name,
    creating another workspace with the same name SHALL be rejected with 409.

    **Validates: Requirements 9.6**
    """
    mock_session = AsyncMock()

    # Simulate an existing workspace with the same name for this user
    existing_ws = mock_workspace(workspace_id=1, user_id=user_id, name=name)

    with patch("app.workspaces.service.repository") as mock_repo:
        mock_repo.get_workspace_by_name_and_user = AsyncMock(return_value=existing_ws)

        data = WorkspaceCreate(name=name)

        with pytest.raises(WorkspaceError) as exc_info:
            await create_workspace(mock_session, user_id, data)

        assert exc_info.value.status_code == 409
        assert name in exc_info.value.detail


@given(
    name=valid_workspace_name_strategy,
    user_id=user_id_strategy,
    workspace_id=workspace_id_strategy,
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property19_unique_name_same_user_accepted(
    name: str, user_id: int, workspace_id: int
) -> None:
    """Property 19: When no existing workspace with the same name exists,
    workspace creation SHALL succeed and return the created workspace.

    **Validates: Requirements 9.6**
    """
    mock_session = AsyncMock()

    new_ws = mock_workspace(workspace_id=workspace_id, user_id=user_id, name=name)

    with patch("app.workspaces.service.repository") as mock_repo:
        mock_repo.get_workspace_by_name_and_user = AsyncMock(return_value=None)
        mock_repo.create_workspace = AsyncMock(return_value=new_ws)

        data = WorkspaceCreate(name=name)
        result = await create_workspace(mock_session, user_id, data)

        assert result.name == name
        assert result.id == workspace_id


# ===========================================================================
# Property 20: Workspace Company Limit Enforcement
# ===========================================================================


@given(
    user_id=user_id_strategy,
    workspace_id=workspace_id_strategy,
    company_id=company_id_strategy,
    company_limit=company_limit_strategy,
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property20_at_limit_addition_rejected(
    user_id: int,
    workspace_id: int,
    company_id: int,
    company_limit: int,
) -> None:
    """Property 20: For any workspace at its configured company limit, adding
    another company SHALL be rejected with 422 indicating current count and max.

    **Validates: Requirements 9.2, 9.3, 20.3**
    """
    mock_session = AsyncMock()

    ws = mock_workspace(workspace_id=workspace_id, user_id=user_id, name="Test", company_limit=company_limit)
    company = mock_company(company_id)

    with patch("app.workspaces.service.repository") as mock_repo:
        mock_repo.get_workspace_by_id_and_user = AsyncMock(return_value=ws)
        mock_repo.get_workspace_company = AsyncMock(return_value=None)  # Not already added
        mock_repo.get_workspace_company_count = AsyncMock(return_value=company_limit)  # At limit

        # Mock SQLAlchemy select for company lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = company
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(WorkspaceError) as exc_info:
            await add_company(mock_session, workspace_id, company_id, user_id)

        error = exc_info.value
        assert error.status_code == 422
        assert str(company_limit) in error.detail  # max limit mentioned
        assert str(company_limit) in error.detail  # current count mentioned


@given(
    user_id=user_id_strategy,
    workspace_id=workspace_id_strategy,
    company_id=company_id_strategy,
    company_limit=company_limit_strategy,
    current_count=st.integers(min_value=0, max_value=19),
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property20_below_limit_addition_allowed(
    user_id: int,
    workspace_id: int,
    company_id: int,
    company_limit: int,
    current_count: int,
) -> None:
    """Property 20: When current count is below the company limit, adding
    a company SHALL succeed without raising a limit error.

    **Validates: Requirements 9.2, 9.3, 20.3**
    """
    # Only test cases where current_count < company_limit
    if current_count >= company_limit:
        return

    mock_session = AsyncMock()
    ws = mock_workspace(workspace_id=workspace_id, user_id=user_id, name="Test", company_limit=company_limit)
    company = mock_company(company_id)

    # Mock workspace detail return for the final get_workspace call
    mock_assoc = MagicMock()
    mock_assoc.added_at = datetime.now(timezone.utc)

    with patch("app.workspaces.service.repository") as mock_repo:
        mock_repo.get_workspace_by_id_and_user = AsyncMock(return_value=ws)
        mock_repo.get_workspace_company = AsyncMock(return_value=None)  # Not already added
        mock_repo.get_workspace_company_count = AsyncMock(return_value=current_count)
        mock_repo.add_company_to_workspace = AsyncMock()
        mock_repo.get_workspace_companies = AsyncMock(return_value=[(company, mock_assoc)])

        # Mock SQLAlchemy select for company lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = company
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Should not raise WorkspaceError with 422
        result = await add_company(mock_session, workspace_id, company_id, user_id)
        assert result is not None


# ===========================================================================
# Property 21: Workspace Add/Remove Integrity
# ===========================================================================


@given(
    user_id=user_id_strategy,
    workspace_id=workspace_id_strategy,
    company_id=company_id_strategy,
    initial_count=st.integers(min_value=0, max_value=2),
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property21_add_increments_count_by_one(
    user_id: int,
    workspace_id: int,
    company_id: int,
    initial_count: int,
) -> None:
    """Property 21: For any Company_Profile added to a workspace, the workspace
    company count SHALL increase by exactly one.

    **Validates: Requirements 10.1, 20.1**
    """
    mock_session = AsyncMock()
    ws = mock_workspace(workspace_id=workspace_id, user_id=user_id, name="Test", company_limit=10)
    company = mock_company(company_id)

    mock_assoc = MagicMock()
    mock_assoc.added_at = datetime.now(timezone.utc)

    # Track count changes
    counts = {"value": initial_count}

    async def mock_add(session, ws_id, c_id):
        counts["value"] += 1

    with patch("app.workspaces.service.repository") as mock_repo:
        mock_repo.get_workspace_by_id_and_user = AsyncMock(return_value=ws)
        mock_repo.get_workspace_company = AsyncMock(return_value=None)
        mock_repo.get_workspace_company_count = AsyncMock(return_value=initial_count)
        mock_repo.add_company_to_workspace = AsyncMock(side_effect=mock_add)
        mock_repo.get_workspace_companies = AsyncMock(return_value=[(company, mock_assoc)])

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = company
        mock_session.execute = AsyncMock(return_value=mock_result)

        await add_company(mock_session, workspace_id, company_id, user_id)

        # Verify count increased by exactly 1
        assert counts["value"] == initial_count + 1
        mock_repo.add_company_to_workspace.assert_called_once_with(
            mock_session, workspace_id, company_id
        )


@given(
    user_id=user_id_strategy,
    workspace_id=workspace_id_strategy,
    company_id=company_id_strategy,
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property21_remove_decrements_count_by_one(
    user_id: int,
    workspace_id: int,
    company_id: int,
) -> None:
    """Property 21: For any company removed from a workspace, the workspace
    company count SHALL decrease by exactly one.

    **Validates: Requirements 10.2, 20.2**
    """
    mock_session = AsyncMock()
    ws = mock_workspace(workspace_id=workspace_id, user_id=user_id, name="Test")

    existing_assoc = MagicMock()
    existing_assoc.workspace_id = workspace_id
    existing_assoc.company_id = company_id

    # Track removal
    removed = {"called": False}

    async def mock_remove(session, ws_id, c_id):
        removed["called"] = True

    with patch("app.workspaces.service.repository") as mock_repo:
        mock_repo.get_workspace_by_id_and_user = AsyncMock(return_value=ws)
        mock_repo.get_workspace_company = AsyncMock(return_value=existing_assoc)
        mock_repo.remove_company_from_workspace = AsyncMock(side_effect=mock_remove)
        mock_repo.get_workspace_companies = AsyncMock(return_value=[])

        await remove_company(mock_session, workspace_id, company_id, user_id)

        # Verify removal was called
        assert removed["called"] is True
        mock_repo.remove_company_from_workspace.assert_called_once_with(
            mock_session, workspace_id, company_id
        )


# ===========================================================================
# Property 22: Duplicate Company in Workspace Rejection
# ===========================================================================


@given(
    user_id=user_id_strategy,
    workspace_id=workspace_id_strategy,
    company_id=company_id_strategy,
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property22_duplicate_company_rejected(
    user_id: int,
    workspace_id: int,
    company_id: int,
) -> None:
    """Property 22: For any Company_Profile already associated with a workspace,
    re-adding it SHALL be rejected with 409 indicating it's already present.

    **Validates: Requirements 10.4, 20.4**
    """
    mock_session = AsyncMock()
    ws = mock_workspace(workspace_id=workspace_id, user_id=user_id, name="Test")

    # Simulate company already in workspace
    existing_assoc = MagicMock()
    existing_assoc.workspace_id = workspace_id
    existing_assoc.company_id = company_id

    company = mock_company(company_id)

    with patch("app.workspaces.service.repository") as mock_repo:
        mock_repo.get_workspace_by_id_and_user = AsyncMock(return_value=ws)
        mock_repo.get_workspace_company = AsyncMock(return_value=existing_assoc)

        # Mock SQLAlchemy select for company lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = company
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(WorkspaceError) as exc_info:
            await add_company(mock_session, workspace_id, company_id, user_id)

        error = exc_info.value
        assert error.status_code == 409
        assert "already" in error.detail.lower()


# ===========================================================================
# Property 23: Multi-Workspace Company Association
# ===========================================================================


@given(
    user_id=user_id_strategy,
    company_id=company_id_strategy,
    num_workspaces=st.integers(min_value=2, max_value=5),
)
@settings(max_examples=30)
@pytest.mark.asyncio
async def test_property23_same_company_in_multiple_workspaces(
    user_id: int,
    company_id: int,
    num_workspaces: int,
) -> None:
    """Property 23: For any Company_Profile, it SHALL be addable to multiple
    distinct workspaces owned by the same user without restriction.

    **Validates: Requirements 10.5, 20.5**
    """
    mock_session = AsyncMock()
    company = mock_company(company_id)

    mock_assoc = MagicMock()
    mock_assoc.added_at = datetime.now(timezone.utc)

    successes = []

    for ws_idx in range(num_workspaces):
        ws_id = ws_idx + 1
        ws = mock_workspace(workspace_id=ws_id, user_id=user_id, name=f"Workspace {ws_id}", company_limit=10)

        with patch("app.workspaces.service.repository") as mock_repo:
            mock_repo.get_workspace_by_id_and_user = AsyncMock(return_value=ws)
            mock_repo.get_workspace_company = AsyncMock(return_value=None)  # Not in this workspace yet
            mock_repo.get_workspace_company_count = AsyncMock(return_value=0)
            mock_repo.add_company_to_workspace = AsyncMock()
            mock_repo.get_workspace_companies = AsyncMock(return_value=[(company, mock_assoc)])

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = company
            mock_session.execute = AsyncMock(return_value=mock_result)

            # Should succeed for each workspace
            result = await add_company(mock_session, ws_id, company_id, user_id)
            successes.append(result is not None)

    # All additions should succeed
    assert all(successes)
    assert len(successes) == num_workspaces
