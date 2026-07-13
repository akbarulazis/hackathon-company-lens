"""Async OpenAI client wrapper for structured and unstructured LLM calls.

Uses gpt-4o-mini as the default model. Handles API errors gracefully
including timeouts, rate limits, and connection errors.
"""

import json
import logging
from typing import Any, TypeVar

from openai import (
    AsyncOpenAI,
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
)
from pydantic import BaseModel

from app.config import Settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_MAX_TOKENS = 4096


class LLMClientError(Exception):
    """Base exception for LLM client errors."""

    pass


class LLMRateLimitError(LLMClientError):
    """Raised when OpenAI rate limit is hit."""

    pass


class LLMTimeoutError(LLMClientError):
    """Raised when OpenAI request times out."""

    pass


class LLMConnectionError(LLMClientError):
    """Raised when connection to OpenAI fails."""

    pass


class LLMClient:
    """Async wrapper around the OpenAI API client.

    Provides methods for both free-form text generation and structured
    JSON output parsing using Pydantic models.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the LLM client with API key from settings.

        Args:
            settings: Application settings containing OPENAI_API_KEY.
        """
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self._model = DEFAULT_MODEL

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        """Generate a text completion from the LLM.

        Args:
            prompt: The user prompt to send.
            system_prompt: Optional system prompt for context/instructions.
            max_tokens: Maximum tokens in the response.

        Returns:
            The generated text content.

        Raises:
            LLMRateLimitError: When rate limit is exceeded.
            LLMTimeoutError: When the request times out.
            LLMConnectionError: When connection fails.
            LLMClientError: For other API errors.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.3,
            )
            content = response.choices[0].message.content
            return content or ""
        except RateLimitError as e:
            logger.warning("OpenAI rate limit exceeded: %s", e)
            raise LLMRateLimitError(f"Rate limit exceeded: {e}") from e
        except APITimeoutError as e:
            logger.warning("OpenAI request timed out: %s", e)
            raise LLMTimeoutError(f"Request timed out: {e}") from e
        except APIConnectionError as e:
            logger.error("OpenAI connection error: %s", e)
            raise LLMConnectionError(f"Connection error: {e}") from e
        except Exception as e:
            logger.error("OpenAI API error: %s", e)
            raise LLMClientError(f"LLM API error: {e}") from e

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> T:
        """Generate a structured response parsed into a Pydantic model.

        Uses JSON mode to ensure the LLM returns valid JSON that can be
        parsed into the provided Pydantic model.

        Args:
            prompt: The user prompt to send.
            response_model: Pydantic model class to parse the response into.
            system_prompt: Optional system prompt for context/instructions.
            max_tokens: Maximum tokens in the response.

        Returns:
            An instance of the response_model populated with LLM output.

        Raises:
            LLMRateLimitError: When rate limit is exceeded.
            LLMTimeoutError: When the request times out.
            LLMConnectionError: When connection fails.
            LLMClientError: For other API errors or JSON parsing failures.
        """
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)

        structured_system = (
            (system_prompt + "\n\n" if system_prompt else "")
            + "You MUST respond with valid JSON matching this schema:\n"
            + schema_json
            + "\n\nRespond ONLY with the JSON object. No markdown, no explanation."
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": structured_system},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return response_model.model_validate_json(content)
        except RateLimitError as e:
            logger.warning("OpenAI rate limit exceeded: %s", e)
            raise LLMRateLimitError(f"Rate limit exceeded: {e}") from e
        except APITimeoutError as e:
            logger.warning("OpenAI request timed out: %s", e)
            raise LLMTimeoutError(f"Request timed out: {e}") from e
        except APIConnectionError as e:
            logger.error("OpenAI connection error: %s", e)
            raise LLMConnectionError(f"Connection error: {e}") from e
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Failed to parse LLM structured output: %s", e)
            raise LLMClientError(f"Failed to parse structured output: {e}") from e
        except Exception as e:
            logger.error("OpenAI API error: %s", e)
            raise LLMClientError(f"LLM API error: {e}") from e
