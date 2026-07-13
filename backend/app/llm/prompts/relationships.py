"""Prompt template for extracting company relationship edges from an acquisition brief.

Extracts up to 20 relationship edges with types:
parent, subsidiary, vendor, customer, partner.
"""

from pydantic import BaseModel, Field


class RelationshipEdge(BaseModel):
    """A single relationship edge between two companies."""

    source: str = Field(description="Name of the source company")
    target: str = Field(description="Name of the target company")
    relation_type: str = Field(
        description="Type of relationship: parent, subsidiary, vendor, customer, or partner"
    )


class RelationshipsOutput(BaseModel):
    """Structured output for relationship extraction.

    Contains a list of up to 20 relationship edges extracted from the brief.
    """

    relationships: list[RelationshipEdge] = Field(
        default_factory=list,
        max_length=20,
        description="List of relationship edges (max 20)",
    )


def build_relationships_system_prompt() -> str:
    """Return the system prompt for relationship extraction."""
    return (
        "You are a corporate intelligence analyst extracting company relationships "
        "from research content. Your job is to identify business relationships between "
        "companies mentioned in the text.\n\n"
        "Relationship types:\n"
        "- parent: Target is a parent/holding company of source\n"
        "- subsidiary: Target is a subsidiary/child company of source\n"
        "- vendor: Target provides goods/services to source\n"
        "- customer: Target is a customer of source\n"
        "- partner: Target has a partnership/alliance with source\n\n"
        "Rules:\n"
        "- Extract at most 20 relationship edges\n"
        "- Only extract relationships explicitly mentioned or strongly implied in the text\n"
        "- Use the exact company names as stated in the text\n"
        "- The source should be the company being researched\n"
        "- Do NOT fabricate relationships that aren't supported by the text\n"
        "- Each edge must have: source (company name), target (company name), "
        "relation_type (one of: parent, subsidiary, vendor, customer, partner)"
    )


def build_relationships_prompt(company_name: str, acquisition_brief: str) -> str:
    """Build the user prompt for relationship extraction.

    Args:
        company_name: Name of the primary company being researched.
        acquisition_brief: The generated acquisition brief markdown text.

    Returns:
        Formatted prompt string ready to send to the LLM.
    """
    return (
        f"Extract company-to-company relationships involving **{company_name}** "
        f"from the following acquisition research brief.\n\n"
        f"For each relationship, specify:\n"
        f"- source: the company name (typically '{company_name}')\n"
        f"- target: the related company name\n"
        f"- relation_type: one of parent, subsidiary, vendor, customer, partner\n\n"
        f"---\n\n"
        f"{acquisition_brief}\n\n"
        f"---\n\n"
        f"Extract up to 20 relationship edges now."
    )
