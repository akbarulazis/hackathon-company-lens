"""Portfolio service orchestrating import, reconciliation, and snapshot storage.

Thin wrapper that delegates heavy lifting to the importer module and
repository layer. Handles resolve_suggestion business logic (marking
suggestion as resolved, optionally storing metrics as a snapshot).

IMPORTANT: Portfolio data is NEVER sent to external LLM APIs.
"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.companies.models import ClientStatus
from app.portfolio import repository
from app.portfolio.importer import derive_products_held, import_portfolio
from app.portfolio.models import PortfolioSnapshot


class PortfolioError(Exception):
    """Domain exception for portfolio operations."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


async def import_file(
    session: AsyncSession,
    file_content: str | bytes,
    filename: str,
    delimiter: str = ",",
    as_of_date: date | None = None,
) -> dict:
    """Import a portfolio CSV/TSV file.

    Delegates to the importer module which handles parsing, reconciliation,
    snapshot storage, client promotion, and group member edge creation.

    Args:
        session: Async database session.
        file_content: Raw file content.
        filename: Original filename (used to detect delimiter).
        delimiter: Column delimiter. Auto-detected from filename if not explicit.
        as_of_date: The snapshot date. Defaults to today.

    Returns:
        Dict with import statistics: matched, unmatched, total, errors.
    """
    # Auto-detect delimiter from filename extension
    if filename.lower().endswith(".tsv"):
        delimiter = "\t"
    elif filename.lower().endswith(".csv"):
        delimiter = ","

    result = await import_portfolio(
        session=session,
        file_content=file_content,
        delimiter=delimiter,
        as_of_date=as_of_date,
    )
    return result


async def get_portfolio(session: AsyncSession, company_id: int) -> dict:
    """Get a company's portfolio data (latest snapshot + history).

    Returns the latest snapshot metrics, all historical snapshots,
    and derived KPIs. Returns appropriate messages if the company
    is not a client or has no portfolio data.

    Args:
        session: Async database session.
        company_id: The company's ID.

    Returns:
        Dict with latest snapshot, history, and portfolio metadata.

    Raises:
        PortfolioError: If company not found or not a client.
    """
    company = await repository.get_company_by_id(session, company_id)
    if company is None:
        raise PortfolioError("Company not found", status_code=404)

    if company.client_status != ClientStatus.client:
        raise PortfolioError(
            "Portfolio data is only available for existing clients",
            status_code=400,
        )

    latest = await repository.get_latest_snapshot(session, company_id)
    history = await repository.get_snapshot_history(session, company_id)

    if latest is None:
        return {
            "company_id": company_id,
            "company_name": company.name,
            "client_status": company.client_status.value,
            "latest_snapshot": None,
            "history": [],
            "products_held": company.products_held or [],
            "message": "No portfolio data has been imported yet",
        }

    return {
        "company_id": company_id,
        "company_name": company.name,
        "client_status": company.client_status.value,
        "latest_snapshot": {
            "id": latest.id,
            "as_of_date": str(latest.as_of_date),
            "metrics": latest.metrics,
        },
        "history": [
            {
                "id": s.id,
                "as_of_date": str(s.as_of_date),
                "metrics": s.metrics,
            }
            for s in history
        ],
        "products_held": company.products_held or [],
        "message": None,
    }


async def resolve_suggestion(
    session: AsyncSession,
    suggestion_id: int,
    resolution: str,
    company_id: int | None = None,
) -> dict:
    """Resolve a portfolio suggestion (accept or reject).

    If accepted with a company_id:
      - Links the suggestion to the company
      - Stores the suggestion's raw_metrics as a new PortfolioSnapshot
      - Promotes the company to Client status if needed
      - Derives products_held from the stored metrics

    Args:
        session: Async database session.
        suggestion_id: The suggestion's ID.
        resolution: Either 'accepted' or 'rejected'.
        company_id: The company to link to (required for 'accepted').

    Returns:
        Dict with resolution result.

    Raises:
        PortfolioError: If suggestion not found or invalid resolution.
    """
    if resolution not in ("accepted", "rejected"):
        raise PortfolioError(
            "Resolution must be 'accepted' or 'rejected'",
            status_code=422,
        )

    if resolution == "accepted" and company_id is None:
        raise PortfolioError(
            "company_id is required when accepting a suggestion",
            status_code=422,
        )

    suggestion = await repository.get_suggestion_by_id(session, suggestion_id)
    if suggestion is None:
        raise PortfolioError("Suggestion not found", status_code=404)

    if suggestion.status != "pending":
        raise PortfolioError(
            f"Suggestion already resolved with status '{suggestion.status}'",
            status_code=409,
        )

    # Resolve the suggestion
    updated = await repository.resolve_suggestion(
        session, suggestion_id, resolution, company_id
    )

    # If accepted, store metrics as a snapshot and promote to client
    if resolution == "accepted" and company_id is not None:
        company = await repository.get_company_by_id(session, company_id)
        if company is None:
            raise PortfolioError(
                f"Company not found: id={company_id}", status_code=404
            )

        # Store raw_metrics as a portfolio snapshot if available
        if suggestion.raw_metrics:
            snapshot = PortfolioSnapshot(
                company_id=company_id,
                as_of_date=suggestion.as_of_date or date.today(),
                metrics=suggestion.raw_metrics,
            )
            session.add(snapshot)

            # Promote to Client if not already
            if company.client_status != ClientStatus.client:
                company.client_status = ClientStatus.client
                if company.client_since is None:
                    company.client_since = (
                        suggestion.as_of_date or date.today()
                    )

            # Derive products-held
            products = derive_products_held(suggestion.raw_metrics)
            company.products_held = products
            session.add(company)

        await session.flush()

    return {
        "id": updated.id,
        "raw_name": updated.raw_name,
        "status": updated.status,
        "matched_company_id": updated.matched_company_id,
        "message": f"Suggestion {resolution} successfully",
    }
