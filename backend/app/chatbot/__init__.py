"""Chatbot module.

Provides RAG chatbot functionality including text chunking,
embedding generation, vector search, and conversational AI.
"""

from app.chatbot.embeddings import (
    chunk_text,
    generate_embeddings,
    search_similar_chunks,
    store_chunks,
)

__all__ = [
    "chunk_text",
    "generate_embeddings",
    "search_similar_chunks",
    "store_chunks",
]
