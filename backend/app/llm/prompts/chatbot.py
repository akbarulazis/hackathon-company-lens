"""Prompt templates for the RAG chatbot.

Builds system and user prompts for the workspace-scoped chatbot.
The chatbot answers questions grounded in company research data
retrieved via vector similarity search, with conversation history
for continuity.
"""

from app.chatbot.models import ChatMessage
from app.documents.models import TextChunk


def build_chatbot_system_prompt() -> str:
    """Return the system prompt for the RAG chatbot.

    Instructs the LLM to answer questions grounded in the provided
    context, citing specific companies when relevant, and indicating
    when information is not available in the context.
    """
    return (
        "You are an AI assistant for corporate banking relationship managers. "
        "Your role is to answer questions about companies in their workspace "
        "based on the provided research context.\n\n"
        "Guidelines:\n"
        "- Answer questions using ONLY the provided context and conversation history\n"
        "- If the context does not contain enough information to answer the question, "
        "say so clearly rather than making up information\n"
        "- Cite specific company names when referencing data from the context\n"
        "- Be concise but thorough — aim for actionable insights\n"
        "- Use professional language appropriate for banking professionals\n"
        "- If asked about topics outside the provided context, politely redirect "
        "to what you can help with based on available company research\n"
        "- Format responses with markdown where appropriate (bullet points, bold, headers)\n"
    )


def build_chatbot_prompt(
    question: str,
    context_chunks: list[TextChunk],
    chat_history: list[ChatMessage],
) -> str:
    """Build the user prompt with retrieved context and conversation history.

    Assembles the prompt with three sections:
    1. Previous conversation messages (last 5) for continuity
    2. Retrieved context chunks from vector search
    3. The current user question

    Args:
        question: The user's current question.
        context_chunks: List of TextChunk objects from similarity search.
        chat_history: List of recent ChatMessage objects for continuity.

    Returns:
        Formatted prompt string ready for LLM invocation.
    """
    sections: list[str] = []

    # Section 1: Conversation history
    if chat_history:
        history_lines = []
        for msg in chat_history:
            role_label = "User" if msg.role == "user" else "Assistant"
            history_lines.append(f"{role_label}: {msg.content}")
        history_text = "\n".join(history_lines)
        sections.append(
            f"## Previous Conversation\n{history_text}"
        )

    # Section 2: Retrieved context
    if context_chunks:
        context_lines = []
        for i, chunk in enumerate(context_chunks, 1):
            context_lines.append(f"[Source {i}]\n{chunk.content}")
        context_text = "\n\n".join(context_lines)
        sections.append(
            f"## Relevant Context\n{context_text}"
        )

    # Section 3: Current question
    sections.append(f"## Current Question\n{question}")

    return "\n\n".join(sections)
