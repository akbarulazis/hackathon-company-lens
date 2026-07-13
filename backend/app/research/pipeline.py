"""Research pipeline orchestrator.

Implements the sequential pipeline: tavily_search → crawl → profile → score →
extract_financials → extract_relationships.

Status state machine: pending → researching → profiling → scoring → ready
(or → failed from any state).

Idempotent: re-running replaces prior data, no duplicates.
"""

import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.companies.models import (
    ClientStatus,
    CompanyProfile,
    CompanyRelationship,
    CompanyStatus,
    RelationType,
    ScoreSnapshot,
)
from app.companies.repository import find_company_by_name_case_insensitive, get_company_by_id
from app.config import Settings
from app.llm.client import LLMClient
from app.llm.prompts.extraction import (
    ExtractionOutput,
    build_extraction_prompt,
    build_extraction_system_prompt,
)
from app.llm.prompts.relationships import (
    RelationshipsOutput,
    build_relationships_prompt,
    build_relationships_system_prompt,
)
from app.llm.prompts.research_brief import (
    MAX_BRIEF_CHARS,
    build_research_brief_prompt,
    build_research_brief_system_prompt,
)
from app.llm.prompts.scoring import (
    ScoringOutput,
    build_scoring_prompt,
    build_scoring_system_prompt,
)
from app.middleware.sanitize import sanitize_html
from app.notifications.events import ResearchStatusEvent
from app.notifications.manager import get_notification_manager
from app.research.crawler import CrawlResult, crawl_urls

logger = logging.getLogger(__name__)

# Tavily API endpoint
TAVILY_SEARCH_URL = "https://api.tavily.com/search"

# Maximum sources from Tavily
MAX_TAVILY_RESULTS = 10

# Maximum relationship edges per run
MAX_RELATIONSHIP_EDGES = 20


class PipelineError(Exception):
    """Raised when a pipeline step fails."""

    def __init__(self, step: str, message: str) -> None:
        self.step = step
        self.message = message
        super().__init__(f"Pipeline failed at step '{step}': {message}")


async def _publish_status(
    user_id: int,
    company_id: int,
    status: str,
    message: str,
) -> None:
    """Publish a research status event via WebSocket."""
    try:
        manager = get_notification_manager()
        event = ResearchStatusEvent(
            company_id=company_id,
            status=status,
            message=message,
        )
        await manager.publish(user_id, event)
    except Exception as e:
        # Don't let notification failures break the pipeline
        logger.warning("Failed to publish status event: %s", e)


async def _update_company_status(
    session: AsyncSession,
    company: CompanyProfile,
    status: CompanyStatus,
) -> None:
    """Update the company's status and persist it."""
    company.status = status
    company.updated_at = datetime.now(UTC)
    await session.flush()


# --- Pipeline Steps ---


async def tavily_search(company_name: str, settings: Settings) -> list[str]:
    """Search Tavily API for web sources about a company.

    Args:
        company_name: Name of the company to search for.
        settings: Application settings containing TAVILY_API_KEY.

    Returns:
        List of URLs from Tavily search results.

    Raises:
        PipelineError: If Tavily returns zero results or API call fails.
    """
    payload = {
        "query": f"{company_name} company profile financials",
        "max_results": MAX_TAVILY_RESULTS,
        "api_key": settings.TAVILY_API_KEY,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                TAVILY_SEARCH_URL,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise PipelineError("tavily_search", f"Tavily API error: {e}") from e

    data = response.json()
    results = data.get("results", [])

    if not results:
        raise PipelineError(
            "tavily_search",
            f"No sources found for '{company_name}'",
        )

    # Extract URLs from results
    urls = [r["url"] for r in results if r.get("url")]
    if not urls:
        raise PipelineError(
            "tavily_search",
            f"No valid URLs in Tavily results for '{company_name}'",
        )

    logger.info("Tavily search returned %d URLs for '%s'", len(urls), company_name)
    return urls


async def crawl_sources(urls: list[str]) -> str:
    """Crawl discovered URLs and assemble content for LLM.

    Args:
        urls: List of URLs to crawl (max 20, depth 2, 30s timeout).

    Returns:
        Concatenated text content from successful crawls.

    Raises:
        PipelineError: If no content could be crawled.
    """
    results: list[CrawlResult] = await crawl_urls(
        urls=urls,
        max_urls=20,
        max_depth=2,
        timeout=30.0,
    )

    # Assemble content from successful crawls
    content_parts: list[str] = []
    for result in results:
        if result.success and result.content:
            content_parts.append(
                f"--- Source: {result.url} ---\n{result.content}"
            )

    if not content_parts:
        raise PipelineError("crawl", "No content could be crawled from discovered URLs")

    combined_content = "\n\n".join(content_parts)
    logger.info(
        "Crawled %d/%d URLs successfully, total content: %d chars",
        len(content_parts),
        len(results),
        len(combined_content),
    )
    return combined_content


async def generate_profile(
    company_name: str, content: str, settings: Settings
) -> str:
    """Generate an acquisition brief using the LLM.

    Args:
        company_name: Name of the company.
        content: Crawled web content.
        settings: Application settings.

    Returns:
        Sanitized markdown acquisition brief (≤50,000 chars).

    Raises:
        PipelineError: If LLM generation fails.
    """
    llm = LLMClient(settings)

    system_prompt = build_research_brief_system_prompt()
    user_prompt = build_research_brief_prompt(company_name, content)

    try:
        brief = await llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=8192,
        )
    except Exception as e:
        raise PipelineError("profile", f"LLM brief generation failed: {e}") from e

    # Sanitize the output
    brief = sanitize_html(brief)

    # Enforce character limit
    if len(brief) > MAX_BRIEF_CHARS:
        brief = brief[:MAX_BRIEF_CHARS]

    logger.info("Generated acquisition brief: %d chars", len(brief))
    return brief


async def score_company(brief: str, settings: Settings) -> ScoringOutput:
    """Score the company across five dimensions using LLM.

    Args:
        brief: The acquisition brief text.
        settings: Application settings.

    Returns:
        ScoringOutput with validated scores (each in [1.0, 5.0]).

    Raises:
        PipelineError: If scoring fails or scores are out of range.
    """
    llm = LLMClient(settings)

    system_prompt = build_scoring_system_prompt()
    user_prompt = build_scoring_prompt(brief)

    try:
        scores = await llm.generate_structured(
            prompt=user_prompt,
            response_model=ScoringOutput,
            system_prompt=system_prompt,
        )
    except Exception as e:
        raise PipelineError("scoring", f"LLM scoring failed: {e}") from e

    # Validate all scores are within [1.0, 5.0]
    dimensions = [
        ("financial_health", scores.financial_health.score),
        ("business_risk", scores.business_risk.score),
        ("growth_potential", scores.growth_potential.score),
        ("product_fit", scores.product_fit.score),
        ("relationship_accessibility", scores.relationship_accessibility.score),
    ]

    for name, value in dimensions:
        if not (1.0 <= value <= 5.0):
            raise PipelineError(
                "scoring",
                f"Score '{name}' out of range: {value} (must be 1.0-5.0)",
            )

    logger.info("Scoring complete: %s", {n: v for n, v in dimensions})
    return scores


async def extract_financials(brief: str, settings: Settings) -> ExtractionOutput:
    """Extract financial fields from the acquisition brief.

    Args:
        brief: The acquisition brief text.
        settings: Application settings.

    Returns:
        ExtractionOutput with extracted financial fields.

    Raises:
        PipelineError: If extraction fails.
    """
    llm = LLMClient(settings)

    system_prompt = build_extraction_system_prompt()
    user_prompt = build_extraction_prompt(brief)

    try:
        extraction = await llm.generate_structured(
            prompt=user_prompt,
            response_model=ExtractionOutput,
            system_prompt=system_prompt,
        )
    except Exception as e:
        raise PipelineError("extract_financials", f"LLM extraction failed: {e}") from e

    logger.info("Financial extraction complete")
    return extraction


async def extract_relationships(
    company_name: str, brief: str, settings: Settings
) -> RelationshipsOutput:
    """Extract relationship edges from the acquisition brief.

    Args:
        company_name: Name of the primary company.
        brief: The acquisition brief text.
        settings: Application settings.

    Returns:
        RelationshipsOutput with up to 20 relationship edges.

    Raises:
        PipelineError: If extraction fails.
    """
    llm = LLMClient(settings)

    system_prompt = build_relationships_system_prompt()
    user_prompt = build_relationships_prompt(company_name, brief)

    try:
        relationships = await llm.generate_structured(
            prompt=user_prompt,
            response_model=RelationshipsOutput,
            system_prompt=system_prompt,
        )
    except Exception as e:
        raise PipelineError(
            "extract_relationships", f"LLM relationship extraction failed: {e}"
        ) from e

    # Enforce max 20 edges
    if len(relationships.relationships) > MAX_RELATIONSHIP_EDGES:
        relationships.relationships = relationships.relationships[:MAX_RELATIONSHIP_EDGES]

    logger.info("Extracted %d relationship edges", len(relationships.relationships))
    return relationships


# --- Idempotency helpers ---


async def _clear_prior_relationships(session: AsyncSession, company_id: int) -> None:
    """Delete prior LLM-extracted relationships for a company (idempotency)."""
    await session.execute(
        delete(CompanyRelationship).where(
            CompanyRelationship.source_id == company_id,
            CompanyRelationship.origin == "llm_extraction",
        )
    )


async def _clear_prior_score_snapshots(session: AsyncSession, company_id: int) -> None:
    """Delete prior score snapshots for a company (idempotency)."""
    await session.execute(
        delete(ScoreSnapshot).where(ScoreSnapshot.company_id == company_id)
    )


# --- Persistence helpers ---


def _parse_revenue_to_float(revenue_str: str | None) -> float | None:
    """Attempt to parse a revenue string like '$50M' to a numeric value."""
    if not revenue_str:
        return None
    # Simple parsing - strip common suffixes
    import re

    match = re.match(r"[\$€£]?\s*([\d,.]+)\s*([KMBT])?", revenue_str, re.IGNORECASE)
    if not match:
        return None

    try:
        value = float(match.group(1).replace(",", ""))
    except (ValueError, TypeError):
        return None

    multiplier_map = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}
    suffix = match.group(2)
    if suffix:
        value *= multiplier_map.get(suffix.upper(), 1)

    return value


async def _persist_scores(
    session: AsyncSession,
    company: CompanyProfile,
    scores: ScoringOutput,
) -> None:
    """Persist scores onto the company profile and create a ScoreSnapshot."""
    # Update company profile scores
    company.financial_health = scores.financial_health.score
    company.business_risk = scores.business_risk.score
    company.growth_potential = scores.growth_potential.score
    company.product_fit = scores.product_fit.score
    company.relationship_accessibility = scores.relationship_accessibility.score

    # Save insights (AI-generated reasoning for each score)
    company.financial_health_insight = scores.financial_health.insight
    company.business_risk_insight = scores.business_risk.insight
    company.growth_potential_insight = scores.growth_potential.insight
    company.product_fit_insight = scores.product_fit.insight
    company.relationship_accessibility_insight = scores.relationship_accessibility.insight

    # Save overall insight and revenue projection
    company.overall_insight = scores.overall_insight
    if hasattr(scores, 'revenue_projection') and scores.revenue_projection:
        company.revenue_projection = scores.revenue_projection.model_dump()

    # Calculate overall score (average of 5 dimensions)
    overall = (
        scores.financial_health.score
        + scores.business_risk.score
        + scores.growth_potential.score
        + scores.product_fit.score
        + scores.relationship_accessibility.score
    ) / 5.0
    company.overall_score = round(overall, 2)

    # Clear prior snapshots (idempotency)
    await _clear_prior_score_snapshots(session, company.id)

    # Create new snapshot
    snapshot = ScoreSnapshot(
        company_id=company.id,
        overall_score=company.overall_score,
        financial_health=scores.financial_health.score,
        business_risk=scores.business_risk.score,
        growth_potential=scores.growth_potential.score,
        product_fit=scores.product_fit.score,
        relationship_accessibility=scores.relationship_accessibility.score,
    )
    session.add(snapshot)
    await session.flush()


async def _persist_financials(
    session: AsyncSession, company: CompanyProfile, extraction: ExtractionOutput
) -> None:
    """Apply extracted financial fields to the company profile and flush."""
    if extraction.founded_year is not None:
        company.founded_year = extraction.founded_year
    if extraction.headquarters is not None:
        company.headquarters = extraction.headquarters
    if extraction.employee_count is not None:
        company.employee_count = extraction.employee_count
    if extraction.annual_revenue is not None:
        company.annual_revenue = _parse_revenue_to_float(extraction.annual_revenue)
    if extraction.funding_total is not None:
        company.funding_total = _parse_revenue_to_float(extraction.funding_total)
    if extraction.market_cap is not None:
        company.market_cap = _parse_revenue_to_float(extraction.market_cap)
    if extraction.company_website is not None:
        company.company_website = extraction.company_website
    if extraction.linkedin_url is not None:
        company.linkedin_url = extraction.linkedin_url
    if extraction.ticker is not None:
        company.ticker = extraction.ticker
    if extraction.industry is not None:
        company.industry = extraction.industry
    await session.flush()
    logger.info(
        "Persisted financials: industry=%s, founded=%s, hq=%s, employees=%s",
        company.industry, company.founded_year, company.headquarters, company.employee_count,
    )


async def _persist_relationships(
    session: AsyncSession,
    company: CompanyProfile,
    relationships: RelationshipsOutput,
) -> None:
    """Persist relationship edges, creating Shell_Company records for unknowns.

    For each relationship edge:
    - If the target company already exists in the DB, link to it.
    - If the target doesn't exist, create a Shell_Company (Client_Status=Unknown).
    """
    # Clear prior LLM-extracted relationships (idempotency)
    await _clear_prior_relationships(session, company.id)

    for edge in relationships.relationships:
        # Determine target company
        target_name = edge.target.strip()
        if not target_name:
            continue

        # Look up the target in the database (case-insensitive)
        target_company = await find_company_by_name_case_insensitive(session, target_name)

        if target_company is None:
            # Create a Shell_Company for the unknown counterparty
            target_company = CompanyProfile(
                name=target_name,
                status=CompanyStatus.pending,
                client_status=ClientStatus.unknown,
            )
            session.add(target_company)
            await session.flush()
            logger.info("Created Shell_Company: '%s' (id=%d)", target_name, target_company.id)

        # Map relation_type string to enum
        try:
            rel_type = RelationType(edge.relation_type.lower())
        except ValueError:
            logger.warning(
                "Unknown relation_type '%s' for edge %s -> %s, skipping",
                edge.relation_type,
                edge.source,
                edge.target,
            )
            continue

        # Create the relationship edge
        relationship = CompanyRelationship(
            source_id=company.id,
            target_id=target_company.id,
            relation_type=rel_type,
            origin="llm_extraction",
            confidence=0.7,  # Default confidence for LLM-extracted edges
        )
        session.add(relationship)

    await session.flush()


# --- Main Orchestrator ---


async def run_pipeline(
    company_id: int,
    user_id: int,
    session: AsyncSession,
    settings: Settings,
) -> None:
    """Execute the full research pipeline for a company.

    Pipeline steps:
    1. tavily_search - Discover web sources
    2. crawl - Crawl discovered URLs
    3. profile - Generate acquisition brief via LLM
    4. score - Score company across 5 dimensions
    5. extract_financials - Extract financial fields
    6. extract_relationships - Extract relationship edges

    Status transitions: pending → researching → profiling → scoring → ready
    On failure at any step: → failed

    Idempotent: re-running replaces prior data (acquisition_brief, scores,
    relationships) rather than creating duplicates.

    Args:
        company_id: ID of the company to research.
        user_id: ID of the user who initiated research.
        session: Async database session.
        settings: Application settings.
    """
    # Load the company profile
    company = await get_company_by_id(session, company_id)
    if company is None:
        logger.error("Company not found: id=%d", company_id)
        return

    company_name = company.name

    try:
        # --- Step 1: Tavily Search (status: researching) ---
        await _update_company_status(session, company, CompanyStatus.researching)
        await _publish_status(
            user_id, company_id, "researching", "Searching for web sources..."
        )

        try:
            urls = await tavily_search(company_name, settings)
        except PipelineError as e:
            if "No sources found" in e.message or "No valid URLs" in e.message:
                # Tavily zero results: set failed, push failure event
                await _update_company_status(session, company, CompanyStatus.failed)
                await _publish_status(
                    user_id,
                    company_id,
                    "failed",
                    f"No sources found for '{company_name}'",
                )
                await session.commit()
                return
            raise

        # --- Step 2: Crawl Sources ---
        crawled_content = await crawl_sources(urls)

        # --- Step 3: Generate Profile (status: profiling) ---
        await _update_company_status(session, company, CompanyStatus.profiling)
        await _publish_status(
            user_id, company_id, "profiling", "Generating acquisition brief..."
        )

        brief = await generate_profile(company_name, crawled_content, settings)

        # Persist the brief (idempotent: replaces prior)
        company.acquisition_brief = brief
        await session.flush()

        # --- Step 4: Score Company (status: scoring) ---
        await _update_company_status(session, company, CompanyStatus.scoring)
        await _publish_status(
            user_id, company_id, "scoring", "Scoring company dimensions..."
        )

        scores = await score_company(brief, settings)
        await _persist_scores(session, company, scores)

        # --- Step 5: Extract Financials ---
        financials = await extract_financials(brief, settings)
        await _persist_financials(session, company, financials)

        # --- Step 6: Extract Relationships ---
        relationships = await extract_relationships(company_name, brief, settings)
        await _persist_relationships(session, company, relationships)

        # --- Step 7: Generate Embeddings for RAG ---
        try:
            from app.chatbot.embeddings import chunk_text, generate_embeddings, store_chunks
            chunks = chunk_text(brief, chunk_size=1000, overlap=200)
            if chunks:
                embeddings = await generate_embeddings(chunks, settings)
                await store_chunks(
                    session=session,
                    company_id=company.id,
                    texts=chunks,
                    embeddings=embeddings,
                    source_type="research",
                )
                logger.info("Generated %d embeddings for company_id=%d", len(chunks), company.id)
        except Exception as embed_err:
            # Embedding failure should not fail the pipeline
            logger.warning("Embedding generation failed for company_id=%d: %s", company.id, embed_err)

        # --- Success: status → ready ---
        await _update_company_status(session, company, CompanyStatus.ready)
        await _publish_status(
            user_id, company_id, "ready", "Research complete"
        )

        await session.commit()
        logger.info("Pipeline completed successfully for company_id=%d", company_id)

    except PipelineError as e:
        await session.rollback()
        logger.error("Pipeline error for company_id=%d: %s", company_id, e)

        # Reload company after rollback
        company = await get_company_by_id(session, company_id)
        if company:
            await _update_company_status(session, company, CompanyStatus.failed)
            await session.commit()

        await _publish_status(
            user_id,
            company_id,
            "failed",
            f"Research failed at step '{e.step}': {e.message}",
        )

    except Exception as e:
        await session.rollback()
        logger.exception("Unexpected error in pipeline for company_id=%d", company_id)

        # Reload company after rollback
        company = await get_company_by_id(session, company_id)
        if company:
            await _update_company_status(session, company, CompanyStatus.failed)
            await session.commit()

        await _publish_status(
            user_id,
            company_id,
            "failed",
            f"Research failed unexpectedly: {str(e)[:200]}",
        )
