"""Property-based tests for resource ownership isolation.

# Feature: company-lens-rebuild
# Property 8: Resource Ownership Isolation

Any workspace-scoped resource request from a non-owner receives a 404 response
identical to a request for a non-existent resource — the existence of other
users' resources is never disclosed.

**Validates: Requirements 3.4, 3.5, 9.5**
"""

import string
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.workspaces.schemas import WorkspaceCreate, WorkspaceUpdate
from app.workspaces.service import (
    WorkspaceError,
    add_company,
    delete_workspace,
    get_workspace,
    remove_company,
    update_workspace,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# User IDs: two distinct users
user_id_pair_strategy = st.tuples(
    st.integers(min_value=1, max_value=100_000),
    st.integers(min_value=1, max_value=100_000),
).filter(lambda pair: pair[0] != pair[1])

# Workspace IDs (simulating existing workspaces)
workspace_id_strategy = st.integers(min_value=1, max_value=100_000)

# Company IDs
company_id_strategy = st.integers(min_value=1, max_value=100_000)

# Non-existent workspace IDs (large range to avoid collision with real ones)
nonexistent_workspace_id_strategy = st.integers(min_value=500_001, max_value=999_999)

# Workspace names for update operations
workspace_name_strategy = st.text(
    alphabet=st.sampled_from(string.ascii_letters + string.digits + " _-"),
    min_size=1,
    max_size=50,
)


# ---------------------------------------------------------------------------
# Helper: mock workspace owned by owner_id but NOT by requester_id
# ---------------------------------------------------------------------------


def mock_workspace_owned_by(owner_id: int, workspace_id: int):
    """Create a mock workspace owned by owner_id."""
    ws = MagicMock()
    ws.id = workspace_id
    ws.user_id = owner_id
    ws.name = "Owner's Workspace"
    ws.company_limit = 3
    return ws


# ===========================================================================
# Property 8: Resource Ownership Isolation
# ===========================================================================


@given(
    user_ids=user_id_pair_strategy,
    workspace_id=workspace_id_strategy,
)
@settings(max_examples=50)
async def test_property8_get_workspace_non_owner_gets_404(
    user_ids: tuple[int, int],
    workspace_id: int,
) -> None:
    """Property 8: When user B (non-owner) tries to get user A's workspace,
    the service SHALL return a 404 identical to a non-existent workspace.

    **Validates: Requirements 3.4, 3.5, 9.5**
    """
    owner_id, non_owner_id = user_ids
    mock_session = AsyncMock()

    with patch("app.workspaces.service.repository") as mock_repo:
        # The repository returns None when queried with non-owner's user_id
        # (the query filters by workspace_id AND user_id)
        mock_repo.get_workspace_by_id_and_user = AsyncMock(return_value=None)

        with pytest.raises(WorkspaceError) as exc_info:
            await get_workspace(mock_session, workspace_id, non_owner_id)

        error = exc_info.value
        assert error.status_code == 404
        assert error.detail == "Workspace not found"


@given(
    user_ids=user_id_pair_strategy,
    workspace_id=workspace_id_strategy,
    nonexistent_id=nonexistent_workspace_id_strategy,
)
@settings(max_examples=50)
async def test_property8_get_response_identical_for_non_owner_and_nonexistent(
    user_ids: tuple[int, int],
    workspace_id: int,
    nonexistent_id: int,
) -> None:
    """Property 8: The 404 response for a non-owner accessing an existing
    workspace SHALL be identical to the 404 for a truly non-existent workspace.

    **Validates: Requirements 3.4, 3.5, 9.5**
    """
    owner_id, non_owner_id = user_ids
    mock_session = AsyncMock()

    with patch("app.workspaces.service.repository") as mock_repo:
        mock_repo.get_workspace_by_id_and_user = AsyncMock(return_value=None)

        # Error from non-owner accessing owner's workspace
        with pytest.raises(WorkspaceError) as exc_non_owner:
            await get_workspace(mock_session, workspace_id, non_owner_id)

        # Error from anyone accessing a non-existent workspace
        with pytest.raises(WorkspaceError) as exc_nonexistent:
            await get_workspace(mock_session, nonexistent_id, non_owner_id)

        # Both responses must be identical
        assert exc_non_owner.value.status_code == exc_nonexistent.value.status_code
        assert exc_non_owner.value.detail == exc_nonexistent.value.detail


@given(
    user_ids=user_id_pair_strategy,
    workspace_id=workspace_id_strategy,
    name=workspace_name_strategy,
)
@settings(max_examples=50)
async def test_property8_update_workspace_non_owner_gets_404(
    user_ids: tuple[int, int],
    workspace_id: int,
    name: str,
) -> None:
    """Property 8: When user B (non-owner) tries to update user A's workspace,
    the service SHALL return a 404 identical to a non-existent workspace.

    **Validates: Requirements 3.4, 3.5, 9.5**
    """
    owner_id, non_owner_id = user_ids
    mock_session = AsyncMock()

    with patch("app.workspaces.service.repository") as mock_repo:
        mock_repo.get_workspace_by_id_and_user = AsyncMock(return_value=None)

        data = WorkspaceUpdate(name=name)

        with pytest.raises(WorkspaceError) as exc_info:
            await update_workspace(mock_session, workspace_id, non_owner_id, data)

        error = exc_info.value
        assert error.status_code == 404
        assert error.detail == "Workspace not found"


@given(
    user_ids=user_id_pair_strategy,
    workspace_id=workspace_id_strategy,
)
@settings(max_examples=50)
async def test_property8_delete_workspace_non_owner_gets_404(
    user_ids: tuple[int, int],
    workspace_id: int,
) -> None:
    """Property 8: When user B (non-owner) tries to delete user A's workspace,
    the service SHALL return a 404 identical to a non-existent workspace.

    **Validates: Requirements 3.4, 3.5, 9.5**
    """
    owner_id, non_owner_id = user_ids
    mock_session = AsyncMock()

    with patch("app.workspaces.service.repository") as mock_repo:
        mock_repo.get_workspace_by_id_and_user = AsyncMock(return_value=None)

        with pytest.raises(WorkspaceError) as exc_info:
            await delete_workspace(mock_session, workspace_id, non_owner_id)

        error = exc_info.value
        assert error.status_code == 404
        assert error.detail == "Workspace not found"


@given(
    user_ids=user_id_pair_strategy,
    workspace_id=workspace_id_strategy,
    company_id=company_id_strategy,
)
@settings(max_examples=50)
async def test_property8_add_company_non_owner_gets_404(
    user_ids: tuple[int, int],
    workspace_id: int,
    company_id: int,
) -> None:
    """Property 8: When user B (non-owner) tries to add a company to user A's
    workspace, the service SHALL return a 404 identical to a non-existent workspace.

    **Validates: Requirements 3.4, 3.5, 9.5**
    """
    owner_id, non_owner_id = user_ids
    mock_session = AsyncMock()

    with patch("app.workspaces.service.repository") as mock_repo:
        mock_repo.get_workspace_by_id_and_user = AsyncMock(return_value=None)

        with pytest.raises(WorkspaceError) as exc_info:
            await add_company(mock_session, workspace_id, company_id, non_owner_id)

        error = exc_info.value
        assert error.status_code == 404
        assert error.detail == "Workspace not found"


@given(
    user_ids=user_id_pair_strategy,
    workspace_id=workspace_id_strategy,
    company_id=company_id_strategy,
)
@settings(max_examples=50)
async def test_property8_remove_company_non_owner_gets_404(
    user_ids: tuple[int, int],
    workspace_id: int,
    company_id: int,
) -> None:
    """Property 8: When user B (non-owner) tries to remove a company from user A's
    workspace, the service SHALL return a 404 identical to a non-existent workspace.

    **Validates: Requirements 3.4, 3.5, 9.5**
    """
    owner_id, non_owner_id = user_ids
    mock_session = AsyncMock()

    with patch("app.workspaces.service.repository") as mock_repo:
        mock_repo.get_workspace_by_id_and_user = AsyncMock(return_value=None)

        with pytest.raises(WorkspaceError) as exc_info:
            await remove_company(mock_session, workspace_id, company_id, non_owner_id)

        error = exc_info.value
        assert error.status_code == 404
        assert error.detail == "Workspace not found"


@given(
    user_ids=user_id_pair_strategy,
    workspace_id=workspace_id_strategy,
    nonexistent_id=nonexistent_workspace_id_strategy,
    company_id=company_id_strategy,
)
@settings(max_examples=50)
async def test_property8_all_operations_indistinguishable_from_nonexistent(
    user_ids: tuple[int, int],
    workspace_id: int,
    nonexistent_id: int,
    company_id: int,
) -> None:
    """Property 8: For ALL workspace operations (get, update, delete,
    add_company, remove_company), the error response for a non-owner
    SHALL be indistinguishable from a truly non-existent resource.

    This verifies the existence of other users' resources is never disclosed.

    **Validates: Requirements 3.4, 3.5, 9.5**
    """
    owner_id, non_owner_id = user_ids
    mock_session = AsyncMock()

    errors_non_owner = []
    errors_nonexistent = []

    with patch("app.workspaces.service.repository") as mock_repo:
        # Both cases return None from the repository
        mock_repo.get_workspace_by_id_and_user = AsyncMock(return_value=None)

        # --- Non-owner accessing an existing workspace ---

        # get
        with pytest.raises(WorkspaceError) as exc:
            await get_workspace(mock_session, workspace_id, non_owner_id)
        errors_non_owner.append((exc.value.status_code, exc.value.detail))

        # update
        with pytest.raises(WorkspaceError) as exc:
            await update_workspace(
                mock_session, workspace_id, non_owner_id, WorkspaceUpdate(name="x")
            )
        errors_non_owner.append((exc.value.status_code, exc.value.detail))

        # delete
        with pytest.raises(WorkspaceError) as exc:
            await delete_workspace(mock_session, workspace_id, non_owner_id)
        errors_non_owner.append((exc.value.status_code, exc.value.detail))

        # add_company
        with pytest.raises(WorkspaceError) as exc:
            await add_company(mock_session, workspace_id, company_id, non_owner_id)
        errors_non_owner.append((exc.value.status_code, exc.value.detail))

        # remove_company
        with pytest.raises(WorkspaceError) as exc:
            await remove_company(mock_session, workspace_id, company_id, non_owner_id)
        errors_non_owner.append((exc.value.status_code, exc.value.detail))

        # --- Anyone accessing a non-existent workspace ---

        # get
        with pytest.raises(WorkspaceError) as exc:
            await get_workspace(mock_session, nonexistent_id, non_owner_id)
        errors_nonexistent.append((exc.value.status_code, exc.value.detail))

        # update
        with pytest.raises(WorkspaceError) as exc:
            await update_workspace(
                mock_session, nonexistent_id, non_owner_id, WorkspaceUpdate(name="x")
            )
        errors_nonexistent.append((exc.value.status_code, exc.value.detail))

        # delete
        with pytest.raises(WorkspaceError) as exc:
            await delete_workspace(mock_session, nonexistent_id, non_owner_id)
        errors_nonexistent.append((exc.value.status_code, exc.value.detail))

        # add_company
        with pytest.raises(WorkspaceError) as exc:
            await add_company(mock_session, nonexistent_id, company_id, non_owner_id)
        errors_nonexistent.append((exc.value.status_code, exc.value.detail))

        # remove_company
        with pytest.raises(WorkspaceError) as exc:
            await remove_company(mock_session, nonexistent_id, company_id, non_owner_id)
        errors_nonexistent.append((exc.value.status_code, exc.value.detail))

    # ALL error responses must be identical
    for i, (non_owner_err, nonexist_err) in enumerate(
        zip(errors_non_owner, errors_nonexistent)
    ):
        assert non_owner_err == nonexist_err, (
            f"Operation {i}: non-owner error {non_owner_err} != "
            f"non-existent error {nonexist_err}"
        )

    # All must be 404 with the same generic message
    for status_code, detail in errors_non_owner:
        assert status_code == 404
        assert detail == "Workspace not found"
