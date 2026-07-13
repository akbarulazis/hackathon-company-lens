"""Unit tests for the LLM client and prompt templates."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm.client import (
    LLMClient,
    LLMClientError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.prompts.extraction import (
    ExtractionOutput,
    build_extraction_prompt,
    build_extraction_system_prompt,
)
from app.llm.prompts.relationships import (
    RelationshipEdge,
    RelationshipsOutput,
    build_relationships_prompt,
    build_relationships_system_prompt,
)
from app.llm.prompts.research_brief import (
    build_research_brief_prompt,
    build_research_brief_system_prompt,
)
from app.llm.prompts.scoring import (
    ScoreDimension,
    ScoringOutput,
    build_scoring_prompt,
    build_scoring_system_prompt,
)


# --- Prompt template tests ---


class TestResearchBriefPrompts:
    def test_system_prompt_contains_key_instructions(self):
        prompt = build_research_brief_system_prompt()
        assert "sanitized markdown" in prompt.lower() or "sanitized" in prompt
        assert "50,000" in prompt
        assert "Executive Summary" in prompt

    def test_user_prompt_includes_company_name(self):
        prompt = build_research_brief_prompt("Acme Corp", "content")
        assert "Acme Corp" in prompt

    def test_user_prompt_includes_crawled_content(self):
        prompt = build_research_brief_prompt("Test Co", "This is crawled data")
        assert "This is crawled data" in prompt

    def test_user_prompt_truncates_long_content(self):
        long_content = "x" * 100_000
        prompt = build_research_brief_prompt("Test Co", long_content)
        assert "[Content truncated]" in prompt
        # Should be truncated to ~80,000 + prompt overhead
        assert len(prompt) < 100_000


class TestScoringPrompts:
    def test_system_prompt_describes_dimensions(self):
        prompt = build_scoring_system_prompt()
        assert "financial_health" in prompt
        assert "business_risk" in prompt
        assert "growth_potential" in prompt
        assert "product_fit" in prompt
        assert "relationship_accessibility" in prompt

    def test_user_prompt_includes_brief(self):
        prompt = build_scoring_prompt("Some brief content")
        assert "Some brief content" in prompt

    def test_scoring_output_validates_valid_scores(self):
        data = {
            "financial_health": {"score": 3.5, "insight": "Good"},
            "business_risk": {"score": 2.0, "insight": "Moderate risk"},
            "growth_potential": {"score": 4.5, "insight": "Strong"},
            "product_fit": {"score": 1.0, "insight": "Poor fit"},
            "relationship_accessibility": {"score": 5.0, "insight": "Excellent"},
        }
        output = ScoringOutput.model_validate(data)
        assert output.financial_health.score == 3.5
        assert output.relationship_accessibility.score == 5.0

    def test_scoring_output_rejects_out_of_range(self):
        data = {
            "financial_health": {"score": 5.5, "insight": "Over max"},
            "business_risk": {"score": 2.0, "insight": "Ok"},
            "growth_potential": {"score": 3.0, "insight": "Ok"},
            "product_fit": {"score": 3.0, "insight": "Ok"},
            "relationship_accessibility": {"score": 3.0, "insight": "Ok"},
        }
        with pytest.raises(Exception):
            ScoringOutput.model_validate(data)

    def test_scoring_output_rejects_below_range(self):
        data = {
            "financial_health": {"score": 0.5, "insight": "Under min"},
            "business_risk": {"score": 2.0, "insight": "Ok"},
            "growth_potential": {"score": 3.0, "insight": "Ok"},
            "product_fit": {"score": 3.0, "insight": "Ok"},
            "relationship_accessibility": {"score": 3.0, "insight": "Ok"},
        }
        with pytest.raises(Exception):
            ScoringOutput.model_validate(data)


class TestExtractionPrompts:
    def test_system_prompt_mentions_null_for_missing(self):
        prompt = build_extraction_system_prompt()
        assert "null" in prompt

    def test_user_prompt_lists_fields(self):
        prompt = build_extraction_prompt("Brief text")
        assert "founded_year" in prompt
        assert "headquarters" in prompt
        assert "employee_count" in prompt
        assert "annual_revenue" in prompt
        assert "industry" in prompt

    def test_extraction_output_with_all_fields(self):
        data = {
            "founded_year": 2010,
            "headquarters": "New York, USA",
            "employee_count": 15000,
            "annual_revenue": "$500M",
            "funding_total": "$200M",
            "market_cap": "$5B",
            "company_website": "https://example.com",
            "linkedin_url": "https://linkedin.com/company/example",
            "ticker": "EXMP",
            "industry": "Technology",
        }
        output = ExtractionOutput.model_validate(data)
        assert output.founded_year == 2010
        assert output.industry == "Technology"

    def test_extraction_output_with_all_nulls(self):
        data = {}
        output = ExtractionOutput.model_validate(data)
        assert output.founded_year is None
        assert output.headquarters is None
        assert output.industry is None


class TestRelationshipsPrompts:
    def test_system_prompt_lists_relation_types(self):
        prompt = build_relationships_system_prompt()
        assert "parent" in prompt
        assert "subsidiary" in prompt
        assert "vendor" in prompt
        assert "customer" in prompt
        assert "partner" in prompt

    def test_user_prompt_includes_company_name(self):
        prompt = build_relationships_prompt("Test Co", "Brief")
        assert "Test Co" in prompt

    def test_relationships_output_validates(self):
        data = {
            "relationships": [
                {"source": "A", "target": "B", "relation_type": "parent"},
                {"source": "A", "target": "C", "relation_type": "vendor"},
            ]
        }
        output = RelationshipsOutput.model_validate(data)
        assert len(output.relationships) == 2
        assert output.relationships[0].relation_type == "parent"

    def test_relationships_output_empty_list(self):
        data = {"relationships": []}
        output = RelationshipsOutput.model_validate(data)
        assert len(output.relationships) == 0

    def test_relationships_output_max_20(self):
        edges = [
            {"source": "A", "target": f"B{i}", "relation_type": "partner"}
            for i in range(21)
        ]
        with pytest.raises(Exception):
            RelationshipsOutput.model_validate({"relationships": edges})


# --- LLM Client tests ---


class TestLLMClient:
    def _make_settings(self):
        """Create a mock settings object."""
        settings = MagicMock()
        settings.OPENAI_API_KEY = "test-key-123"
        return settings

    @pytest.mark.asyncio
    async def test_generate_returns_content(self):
        settings = self._make_settings()
        client = LLMClient(settings)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated text"

        with patch.object(
            client._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = await client.generate("test prompt")

        assert result == "Generated text"

    @pytest.mark.asyncio
    async def test_generate_with_system_prompt(self):
        settings = self._make_settings()
        client = LLMClient(settings)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"

        with patch.object(
            client._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            await client.generate("user prompt", system_prompt="system instructions")

            call_args = mock_create.call_args
            messages = call_args.kwargs["messages"]
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "system instructions"
            assert messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_generate_structured_returns_model(self):
        settings = self._make_settings()
        client = LLMClient(settings)

        extraction_json = json.dumps({
            "founded_year": 2020,
            "headquarters": "London, UK",
            "employee_count": 500,
            "annual_revenue": "$10M",
            "funding_total": None,
            "market_cap": None,
            "company_website": "https://test.com",
            "linkedin_url": None,
            "ticker": None,
            "industry": "Fintech",
        })

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = extraction_json

        with patch.object(
            client._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = await client.generate_structured(
                "Extract fields", ExtractionOutput
            )

        assert isinstance(result, ExtractionOutput)
        assert result.founded_year == 2020
        assert result.industry == "Fintech"

    @pytest.mark.asyncio
    async def test_generate_handles_rate_limit(self):
        from openai import RateLimitError

        settings = self._make_settings()
        client = LLMClient(settings)

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        with patch.object(
            client._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = RateLimitError(
                "Rate limit", response=mock_response, body=None
            )
            with pytest.raises(LLMRateLimitError):
                await client.generate("test")

    @pytest.mark.asyncio
    async def test_generate_handles_timeout(self):
        from openai import APITimeoutError

        settings = self._make_settings()
        client = LLMClient(settings)

        with patch.object(
            client._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = APITimeoutError(request=MagicMock())
            with pytest.raises(LLMTimeoutError):
                await client.generate("test")

    @pytest.mark.asyncio
    async def test_generate_handles_connection_error(self):
        from openai import APIConnectionError

        settings = self._make_settings()
        client = LLMClient(settings)

        with patch.object(
            client._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = APIConnectionError(request=MagicMock())
            with pytest.raises(LLMConnectionError):
                await client.generate("test")

    @pytest.mark.asyncio
    async def test_generate_structured_handles_invalid_json(self):
        settings = self._make_settings()
        client = LLMClient(settings)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not valid json {{"

        with patch.object(
            client._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            with pytest.raises(LLMClientError):
                await client.generate_structured("test", ExtractionOutput)

    @pytest.mark.asyncio
    async def test_generate_returns_empty_on_none_content(self):
        settings = self._make_settings()
        client = LLMClient(settings)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None

        with patch.object(
            client._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = await client.generate("test")

        assert result == ""
