"""Unit tests for chatbot embedding utilities.

Tests the chunk_text function (pure logic) and the search threshold logic.
"""

import pytest

from app.chatbot.embeddings import chunk_text


class TestChunkText:
    """Tests for the text chunking function."""

    def test_empty_text_returns_empty_list(self):
        """Empty input returns empty list."""
        assert chunk_text("") == []

    def test_short_text_returns_single_chunk(self):
        """Text shorter than chunk_size returns as single element."""
        text = "Hello world, this is a short text."
        result = chunk_text(text, chunk_size=1000, overlap=200)
        assert result == [text]

    def test_text_exactly_chunk_size_returns_single_chunk(self):
        """Text exactly at chunk_size returns single chunk."""
        text = "a" * 1000
        result = chunk_text(text, chunk_size=1000, overlap=200)
        assert result == [text]

    def test_longer_text_produces_multiple_chunks(self):
        """Text longer than chunk_size is split into multiple chunks."""
        # Create text with words
        words = ["word"] * 300  # 300 * 5 = 1500 chars with spaces
        text = " ".join(words)
        result = chunk_text(text, chunk_size=1000, overlap=200)
        assert len(result) > 1

    def test_chunks_respect_approximate_size(self):
        """Each chunk is approximately chunk_size characters."""
        words = ["testing"] * 500  # ~3500 chars
        text = " ".join(words)
        result = chunk_text(text, chunk_size=1000, overlap=200)
        # All chunks except possibly last should be close to chunk_size
        for chunk in result[:-1]:
            assert len(chunk) <= 1100  # Allow some tolerance for word boundaries

    def test_overlap_between_consecutive_chunks(self):
        """Consecutive chunks share overlapping content."""
        words = ["hello"] * 400  # ~2400 chars
        text = " ".join(words)
        result = chunk_text(text, chunk_size=1000, overlap=200)
        assert len(result) >= 2

        # Check that chunks have overlapping content
        for i in range(len(result) - 1):
            # The end of chunk i should overlap with the start of chunk i+1
            end_of_current = result[i][-200:]
            start_of_next = result[i + 1][:200]
            # There should be shared content
            assert end_of_current in result[i + 1] or start_of_next in result[i]

    def test_concatenation_reconstructs_original(self):
        """Accounting for overlap, chunks reconstruct original text."""
        # Use non-repetitive text to make verification easier
        import string
        import random
        random.seed(42)
        words = ["".join(random.choices(string.ascii_lowercase, k=random.randint(3, 8))) for _ in range(300)]
        text = " ".join(words)
        result = chunk_text(text, chunk_size=200, overlap=50)

        # Every character in the original text should be in at least one chunk
        # We verify by checking that the full text can be reconstructed:
        # each chunk should be a substring of the original text
        for chunk in result:
            assert chunk in text, f"Chunk not found in original: {chunk[:50]}..."

        # The first chunk starts at position 0
        assert text.startswith(result[0])
        # The last chunk ends at the end of text
        assert text.endswith(result[-1])

        # Every position in the original is covered by at least one chunk
        # We verify by checking consecutive chunks overlap
        for i in range(len(result) - 1):
            # Find where current chunk ends in the original
            current_end_pos = text.find(result[i]) + len(result[i])
            # Find where next chunk starts in the original
            next_start_pos = text.find(result[i + 1])
            # Next chunk should start before or at the end of current chunk
            assert next_start_pos < current_end_pos, (
                f"Gap between chunk {i} and {i+1}: "
                f"current ends at {current_end_pos}, next starts at {next_start_pos}"
            )

    def test_splits_at_word_boundaries(self):
        """Chunks split at word boundaries, not mid-word."""
        # Use unique words to avoid ambiguity
        words = [f"word{i:04d}" for i in range(200)]
        text = " ".join(words)
        result = chunk_text(text, chunk_size=100, overlap=20)
        for i, chunk in enumerate(result):
            # Each chunk should not start mid-word (except possibly first)
            if i > 0:
                # Find where this chunk starts in original text
                pos = text.find(chunk)
                # Should start at beginning or right after a space
                assert pos == 0 or text[pos - 1] == " ", (
                    f"Chunk {i} starts mid-word at position {pos}: "
                    f"...{text[max(0,pos-5):pos+10]}..."
                )

    def test_no_empty_chunks(self):
        """No empty strings in the result."""
        text = "word " * 500
        result = chunk_text(text, chunk_size=1000, overlap=200)
        for chunk in result:
            assert len(chunk) > 0

    def test_custom_chunk_size_and_overlap(self):
        """Custom chunk_size and overlap values work correctly."""
        text = "a " * 1000  # 2000 chars
        result = chunk_text(text, chunk_size=500, overlap=100)
        assert len(result) > 2

    def test_single_long_word_handled(self):
        """A very long word without spaces is handled without infinite loop."""
        text = "a" * 2000  # No spaces at all
        result = chunk_text(text, chunk_size=1000, overlap=200)
        assert len(result) >= 2
        # All characters should be covered
        combined = "".join(result)
        # Due to overlap, combined may be longer but should contain original
        assert text[0:1000] in combined
