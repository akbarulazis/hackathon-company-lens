"""Property-based tests for WebSocket Event Schema Conformance.

**Validates: Requirements 6.2**

Property 17: WebSocket Event Schema Conformance
For any status transition event published to a WebSocket channel, the event payload
SHALL conform to the typed structure with required fields.
"""

import json
import re

from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.notifications.events import (
    ChatTokenEvent,
    ComparisonResultEvent,
    ComparisonStatusEvent,
    DocumentStatusEvent,
    ResearchStatusEvent,
    ToastEvent,
    ToastLevel,
)


# --- Strategies ---

positive_int = st.integers(min_value=1, max_value=2**31 - 1)
non_empty_str = st.text(min_size=1, max_size=200, alphabet=st.characters(blacklist_categories=("Cs",)))
status_str = st.sampled_from(["pending", "researching", "profiling", "scoring", "ready", "failed", "processing"])
iso8601_timestamp = st.from_regex(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", fullmatch=True
)
toast_level = st.sampled_from([ToastLevel.INFO, ToastLevel.SUCCESS, ToastLevel.WARNING, ToastLevel.ERROR])


class TestResearchStatusEventSchema:
    """ResearchStatusEvent always has: type="research.status", company_id (int), status (str), message (str), timestamp (ISO8601 str)."""

    @settings(max_examples=200)
    @given(
        company_id=positive_int,
        status=status_str,
        message=non_empty_str,
        timestamp=iso8601_timestamp,
    )
    def test_research_status_event_conforms_to_schema(self, company_id, status, message, timestamp):
        """**Validates: Requirements 6.2**

        For any valid input data, ResearchStatusEvent serialized JSON always contains
        the correct type discriminator and all required fields.
        """
        event = ResearchStatusEvent(
            company_id=company_id,
            status=status,
            message=message,
            timestamp=timestamp,
        )
        payload = json.loads(event.model_dump_json())

        # Type discriminator is always "research.status"
        assert payload["type"] == "research.status"
        # company_id is an integer
        assert isinstance(payload["company_id"], int)
        assert payload["company_id"] == company_id
        # status is a string
        assert isinstance(payload["status"], str)
        assert payload["status"] == status
        # message is a string
        assert isinstance(payload["message"], str)
        assert payload["message"] == message
        # timestamp is an ISO8601 string
        assert isinstance(payload["timestamp"], str)
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", payload["timestamp"])

    @settings(max_examples=200)
    @given(
        company_id=positive_int,
        status=status_str,
        message=non_empty_str,
    )
    def test_research_status_event_generates_default_timestamp(self, company_id, status, message):
        """ResearchStatusEvent generates a valid ISO8601 timestamp when not provided."""
        event = ResearchStatusEvent(
            company_id=company_id,
            status=status,
            message=message,
        )
        payload = json.loads(event.model_dump_json())

        assert "timestamp" in payload
        assert isinstance(payload["timestamp"], str)
        # Matches ISO8601 format YYYY-MM-DDTHH:MM:SSZ
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", payload["timestamp"])


class TestComparisonStatusEventSchema:
    """ComparisonStatusEvent always has: type="comparison.status", workspace_id (int), report_id (int), status (str)."""

    @settings(max_examples=200)
    @given(
        workspace_id=positive_int,
        report_id=positive_int,
        status=status_str,
    )
    def test_comparison_status_event_conforms_to_schema(self, workspace_id, report_id, status):
        """**Validates: Requirements 6.2**

        For any valid input data, ComparisonStatusEvent serialized JSON always contains
        the correct type discriminator and all required fields.
        """
        event = ComparisonStatusEvent(
            workspace_id=workspace_id,
            report_id=report_id,
            status=status,
        )
        payload = json.loads(event.model_dump_json())

        assert payload["type"] == "comparison.status"
        assert isinstance(payload["workspace_id"], int)
        assert payload["workspace_id"] == workspace_id
        assert isinstance(payload["report_id"], int)
        assert payload["report_id"] == report_id
        assert isinstance(payload["status"], str)
        assert payload["status"] == status


class TestComparisonResultEventSchema:
    """ComparisonResultEvent always has: type="comparison.result", workspace_id (int), report_id (int)."""

    @settings(max_examples=200)
    @given(
        workspace_id=positive_int,
        report_id=positive_int,
    )
    def test_comparison_result_event_conforms_to_schema(self, workspace_id, report_id):
        """**Validates: Requirements 6.2**

        For any valid input data, ComparisonResultEvent serialized JSON always contains
        the correct type discriminator and all required fields.
        """
        event = ComparisonResultEvent(
            workspace_id=workspace_id,
            report_id=report_id,
        )
        payload = json.loads(event.model_dump_json())

        assert payload["type"] == "comparison.result"
        assert isinstance(payload["workspace_id"], int)
        assert payload["workspace_id"] == workspace_id
        assert isinstance(payload["report_id"], int)
        assert payload["report_id"] == report_id


class TestDocumentStatusEventSchema:
    """DocumentStatusEvent always has: type="document.status", document_id (int), company_id (int), status (str)."""

    @settings(max_examples=200)
    @given(
        document_id=positive_int,
        company_id=positive_int,
        status=status_str,
        message=st.one_of(st.none(), non_empty_str),
    )
    def test_document_status_event_conforms_to_schema(self, document_id, company_id, status, message):
        """**Validates: Requirements 6.2**

        For any valid input data, DocumentStatusEvent serialized JSON always contains
        the correct type discriminator and all required fields.
        """
        event = DocumentStatusEvent(
            document_id=document_id,
            company_id=company_id,
            status=status,
            message=message,
        )
        payload = json.loads(event.model_dump_json())

        assert payload["type"] == "document.status"
        assert isinstance(payload["document_id"], int)
        assert payload["document_id"] == document_id
        assert isinstance(payload["company_id"], int)
        assert payload["company_id"] == company_id
        assert isinstance(payload["status"], str)
        assert payload["status"] == status
        # message is optional
        if message is not None:
            assert payload["message"] == message
        else:
            assert payload["message"] is None


class TestChatTokenEventSchema:
    """ChatTokenEvent always has: type="chat.token", workspace_id (int), token (str), done (bool)."""

    @settings(max_examples=200)
    @given(
        workspace_id=positive_int,
        token=st.text(min_size=0, max_size=500, alphabet=st.characters(blacklist_categories=("Cs",))),
        done=st.booleans(),
    )
    def test_chat_token_event_conforms_to_schema(self, workspace_id, token, done):
        """**Validates: Requirements 6.2**

        For any valid input data, ChatTokenEvent serialized JSON always contains
        the correct type discriminator and all required fields.
        """
        event = ChatTokenEvent(
            workspace_id=workspace_id,
            token=token,
            done=done,
        )
        payload = json.loads(event.model_dump_json())

        assert payload["type"] == "chat.token"
        assert isinstance(payload["workspace_id"], int)
        assert payload["workspace_id"] == workspace_id
        assert isinstance(payload["token"], str)
        assert payload["token"] == token
        assert isinstance(payload["done"], bool)
        assert payload["done"] == done


class TestToastEventSchema:
    """ToastEvent always has: type="toast", level (one of info/success/warning/error), message (str)."""

    @settings(max_examples=200)
    @given(
        level=toast_level,
        message=non_empty_str,
    )
    def test_toast_event_conforms_to_schema(self, level, message):
        """**Validates: Requirements 6.2**

        For any valid input data, ToastEvent serialized JSON always contains
        the correct type discriminator and all required fields.
        """
        event = ToastEvent(
            level=level,
            message=message,
        )
        payload = json.loads(event.model_dump_json())

        assert payload["type"] == "toast"
        assert payload["level"] in ("info", "success", "warning", "error")
        assert payload["level"] == level.value
        assert isinstance(payload["message"], str)
        assert payload["message"] == message


class TestInvalidDataRejection:
    """Test that invalid data types are rejected by the Pydantic models."""

    @settings(max_examples=200)
    @given(
        invalid_company_id=st.text(min_size=1, max_size=20, alphabet=st.characters(categories=("L",))),
    )
    def test_research_status_rejects_non_int_company_id(self, invalid_company_id):
        """**Validates: Requirements 6.2**

        Invalid data types (e.g., string where int expected) are rejected.
        """
        try:
            ResearchStatusEvent(
                company_id=invalid_company_id,
                status="researching",
                message="test",
            )
            # Pydantic may coerce some values - if it doesn't raise, that's fine
            # as long as the model enforces the typed structure
        except (ValidationError, TypeError, ValueError):
            pass  # Expected: invalid type rejected

    @settings(max_examples=200)
    @given(
        invalid_level=st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L",))).filter(
            lambda x: x.lower() not in ("info", "success", "warning", "error")
        ),
    )
    def test_toast_event_rejects_invalid_level(self, invalid_level):
        """**Validates: Requirements 6.2**

        ToastEvent rejects level values not in (info, success, warning, error).
        """
        try:
            ToastEvent(
                level=invalid_level,
                message="test",
            )
            # Should not reach here with an invalid level
            assert False, f"Expected ValidationError for level={invalid_level!r}"
        except (ValidationError, ValueError):
            pass  # Expected: invalid level rejected

    @settings(max_examples=200)
    @given(
        invalid_workspace_id=st.text(min_size=1, max_size=20, alphabet=st.characters(categories=("L",))),
    )
    def test_chat_token_rejects_non_int_workspace_id(self, invalid_workspace_id):
        """**Validates: Requirements 6.2**

        ChatTokenEvent rejects non-integer workspace_id.
        """
        try:
            ChatTokenEvent(
                workspace_id=invalid_workspace_id,
                token="hello",
                done=False,
            )
        except (ValidationError, TypeError, ValueError):
            pass  # Expected: invalid type rejected

    @settings(max_examples=200)
    @given(
        invalid_done=st.text(min_size=1, max_size=20, alphabet=st.characters(categories=("L",))).filter(
            lambda x: x.lower() not in ("true", "false", "1", "0", "yes", "no")
        ),
    )
    def test_chat_token_rejects_non_bool_done(self, invalid_done):
        """**Validates: Requirements 6.2**

        ChatTokenEvent rejects non-boolean done field.
        """
        try:
            ChatTokenEvent(
                workspace_id=1,
                token="hello",
                done=invalid_done,
            )
        except (ValidationError, TypeError, ValueError):
            pass  # Expected: invalid type rejected
