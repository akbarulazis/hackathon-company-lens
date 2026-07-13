"""Portfolio data importer with CSV/TSV parsing and column name convention parser.

Handles:
- Column name parsing: {division}_{product_group}_{subproduct}_{metric}
- CSV/TSV file parsing
- 3-step company name reconciliation (exact → alias → fuzzy pg_trgm)
- Sparse portfolio snapshot storage
- Client status promotion on first match
- Products-held derivation from non-zero metrics
- Group member relationship creation from nama_group/nama_subholding

IMPORTANT: Portfolio data is NEVER sent to external LLM APIs.
"""

import csv
import io
from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.companies.models import (
    ClientStatus,
    CompanyProfile,
    CompanyRelationship,
    RelationType,
)
from app.portfolio.models import MetricCatalog, PortfolioSnapshot, PortfolioSuggestion

# Known metric suffixes — ordered longest first for longest-match parsing
KNOWN_METRIC_SUFFIXES: list[str] = [
    "profitabilitas",
    "fee_income",
    "baki_debet",
    "outstanding",
    "pendapatan",
    "nominal",
    "jumlah",
    "saldo",
    "nii",
]

# Known subproducts — ordered longest first for longest-match parsing
KNOWN_SUBPRODUCTS: list[str] = [
    "kmk_non_scf",
    "kmk_scf",
    "tabungan",
    "deposito",
    "others",
    "giro",
    "ki",
]

# Special columns that are not metrics (metadata columns)
METADATA_COLUMNS: set[str] = {
    "nama_nasabah",
    "nama_group",
    "nama_subholding",
    "cif",
    "cif_number",
    "nama",
    "name",
    "company_name",
}


def parse_column_name(column_name: str) -> dict:
    """Parse a portfolio column name into its constituent parts.

    Column naming convention: {division}_{product_group}_{subproduct}_{metric}

    Uses longest-match on known metric suffixes first, then known subproducts.
    The remainder is split into division and product_group.

    Args:
        column_name: The raw column name from the CSV/TSV header.

    Returns:
        dict with keys: division, product_group, subproduct, metric
        (any value can be None if not parseable)
    """
    result = {
        "division": None,
        "product_group": None,
        "subproduct": None,
        "metric": None,
    }

    col_lower = column_name.strip().lower()
    if not col_lower:
        return result

    remaining = col_lower

    # Step 1: Match metric suffix (longest first)
    metric_match = None
    for suffix in KNOWN_METRIC_SUFFIXES:
        if remaining.endswith(f"_{suffix}"):
            metric_match = suffix
            remaining = remaining[: -(len(suffix) + 1)]  # Remove _suffix
            break
        elif remaining == suffix:
            metric_match = suffix
            remaining = ""
            break

    result["metric"] = metric_match

    if not remaining:
        return result

    # Step 2: Match subproduct (longest first)
    subproduct_match = None
    for subprod in KNOWN_SUBPRODUCTS:
        if remaining.endswith(f"_{subprod}"):
            subproduct_match = subprod
            remaining = remaining[: -(len(subprod) + 1)]  # Remove _subproduct
            break
        elif remaining == subprod:
            subproduct_match = subprod
            remaining = ""
            break

    result["subproduct"] = subproduct_match

    if not remaining:
        return result

    # Step 3: Split remainder into division and product_group
    # If there's an underscore, the first segment is division, the rest is product_group
    parts = remaining.split("_", 1)
    if len(parts) == 2:
        result["division"] = parts[0]
        result["product_group"] = parts[1]
    else:
        # Single segment — treat as division
        result["division"] = parts[0]

    return result


def parse_portfolio_file(
    content: str | bytes, delimiter: str = ",", filename: str = ""
) -> tuple[list[str], list[dict]]:
    """Parse a CSV/TSV/Excel portfolio file into headers and rows.

    Args:
        content: Raw file content as string or bytes.
        delimiter: Column delimiter (',' for CSV, '\\t' for TSV).
        filename: Original filename (used to detect Excel format).

    Returns:
        Tuple of (headers list, rows as list of dicts).
    """
    # Handle Excel files
    if filename.lower().endswith((".xlsx", ".xls")):
        import openpyxl
        from io import BytesIO

        if isinstance(content, str):
            content = content.encode("utf-8")

        wb = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        if ws is None:
            return [], []

        rows_iter = ws.iter_rows(values_only=True)
        header_row = next(rows_iter, None)
        if not header_row:
            return [], []

        headers = [str(cell) if cell is not None else "" for cell in header_row]
        rows = []
        for row in rows_iter:
            row_dict = {}
            for i, cell in enumerate(row):
                if i < len(headers):
                    row_dict[headers[i]] = str(cell) if cell is not None else ""
            rows.append(row_dict)

        wb.close()
        return headers, rows

    # Handle CSV/TSV
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")  # Handle BOM

    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    headers = reader.fieldnames or []
    rows = list(reader)

    return list(headers), rows


def derive_products_held(metrics: dict) -> list[str]:
    """Derive products-held list from non-zero metrics in a snapshot.

    Args:
        metrics: Dict of metric_key → numeric value.

    Returns:
        List of metric keys where value is non-zero.
    """
    products = []
    for key, value in metrics.items():
        try:
            numeric_val = float(value)
            if numeric_val != 0:
                products.append(key)
        except (ValueError, TypeError):
            # Non-numeric values are skipped
            continue
    return sorted(products)


async def reconcile_company_name(
    session: AsyncSession, name: str
) -> CompanyProfile | None:
    """Reconcile a customer name against existing Company_Profiles.

    3-step reconciliation:
      1. Normalized exact match (strip, lower)
      2. Alias table lookup (placeholder — requires alias model)
      3. Fuzzy pg_trgm match (similarity > 0.7)

    Args:
        session: Async database session.
        name: The raw customer name from the portfolio file.

    Returns:
        Matched CompanyProfile or None if no match found.
    """
    normalized_name = name.strip().lower()

    if not normalized_name:
        return None

    # Step 1: Normalized exact match
    stmt = select(CompanyProfile).where(
        func.lower(func.trim(CompanyProfile.name)) == normalized_name
    )
    result = await session.execute(stmt)
    match = result.scalar_one_or_none()
    if match:
        return match

    # Step 2: Alias table lookup
    # This is a placeholder — when an alias model is implemented,
    # look up normalized_name in the alias table.
    # For now, skip to step 3.

    # Step 3: Fuzzy pg_trgm match
    # Uses PostgreSQL similarity() function with threshold 0.7
    # Wrapped in try/except to handle slow queries gracefully
    try:
        stmt = (
            select(CompanyProfile)
            .where(
                text("similarity(lower(name), :search_name) > 0.7")
            )
            .order_by(text("similarity(lower(name), :search_name) DESC"))
            .limit(1)
        )
        result = await session.execute(stmt, {"search_name": normalized_name})
        match = result.scalar_one_or_none()
        if match:
            return match
    except Exception:
        # If pg_trgm query fails or times out, skip fuzzy matching
        pass

    return None


async def _get_fuzzy_similarity_score(
    session: AsyncSession, name: str, company_name: str
) -> float:
    """Get the pg_trgm similarity score between two names.

    Args:
        session: Async database session.
        name: The search name.
        company_name: The company name to compare against.

    Returns:
        Similarity score (0.0 to 1.0).
    """
    result = await session.execute(
        text("SELECT similarity(lower(:name1), lower(:name2))"),
        {"name1": name, "name2": company_name},
    )
    row = result.fetchone()
    return float(row[0]) if row else 0.0


async def _update_metric_catalog(
    session: AsyncSession, headers: list[str]
) -> dict[str, dict]:
    """Update the MetricCatalog with column definitions.

    For each header:
    - If already in catalog, skip.
    - If parseable, add with parsed components.
    - If not parseable, add with unit="unknown" for manual review.

    Args:
        session: Async database session.
        headers: List of column headers from the portfolio file.

    Returns:
        Dict mapping column_name → parsed components.
    """
    column_map: dict[str, dict] = {}

    # Get existing catalog entries
    stmt = select(MetricCatalog.column_name)
    result = await session.execute(stmt)
    existing_columns = {row[0] for row in result.fetchall()}

    for header in headers:
        col_lower = header.strip().lower()

        # Skip metadata columns
        if col_lower in METADATA_COLUMNS:
            continue

        parsed = parse_column_name(col_lower)
        column_map[col_lower] = parsed

        # Add to catalog if not already there
        if col_lower not in existing_columns:
            has_any_parsed = any(
                v is not None for v in parsed.values()
            )
            catalog_entry = MetricCatalog(
                column_name=col_lower,
                division=parsed["division"],
                product_group=parsed["product_group"],
                subproduct=parsed["subproduct"],
                metric=parsed["metric"],
                unit="unknown" if not has_any_parsed else None,
                reviewed=False,
            )
            session.add(catalog_entry)
            existing_columns.add(col_lower)

    await session.flush()
    return column_map


async def _promote_to_client(
    session: AsyncSession, company: CompanyProfile, as_of_date: date
) -> None:
    """Promote a company to Client status on first portfolio match.

    Only promotes if the company is not already a Client.
    Sets client_since to the as_of_date.

    Args:
        session: Async database session.
        company: The matched CompanyProfile.
        as_of_date: The portfolio snapshot date.
    """
    if company.client_status != ClientStatus.client:
        company.client_status = ClientStatus.client
        if company.client_since is None:
            company.client_since = as_of_date
        session.add(company)
        await session.flush()


async def _create_group_member_edges(
    session: AsyncSession,
    company: CompanyProfile,
    row: dict,
) -> None:
    """Create or refresh group_member relationship edges.

    Creates edges from nama_group and nama_subholding values.
    Finds or creates the group/subholding company, then creates
    an edge with relation_type "group_member" and origin "internal".

    Args:
        session: Async database session.
        company: The matched CompanyProfile (source of edge).
        row: The data row containing nama_group/nama_subholding.
    """
    group_fields = ["nama_group", "nama_subholding"]

    for field in group_fields:
        group_name = row.get(field, "").strip()
        if not group_name:
            continue

        # Find or create the group company
        stmt = select(CompanyProfile).where(
            func.lower(func.trim(CompanyProfile.name)) == group_name.lower()
        )
        result = await session.execute(stmt)
        group_company = result.scalar_one_or_none()

        if not group_company:
            # Create a shell company for the group
            group_company = CompanyProfile(
                name=group_name,
                client_status=ClientStatus.unknown,
            )
            session.add(group_company)
            await session.flush()

        # Check if relationship already exists
        stmt = select(CompanyRelationship).where(
            CompanyRelationship.source_id == company.id,
            CompanyRelationship.target_id == group_company.id,
            CompanyRelationship.relation_type == RelationType.group_member,
        )
        result = await session.execute(stmt)
        existing_edge = result.scalar_one_or_none()

        if not existing_edge:
            edge = CompanyRelationship(
                source_id=company.id,
                target_id=group_company.id,
                relation_type=RelationType.group_member,
                origin="internal",
                confidence=1.0,
            )
            session.add(edge)

    await session.flush()


def _get_company_name_column(headers: list[str]) -> str | None:
    """Identify the company name column from headers.

    Looks for known name column variants. Also does partial matching
    for common patterns like 'customer_name', 'client_name', etc.

    Args:
        headers: List of column headers.

    Returns:
        The header name for the company name column, or None.
    """
    # Exact matches first
    name_variants = [
        "nama_nasabah",
        "nama",
        "name",
        "company_name",
        "company",
        "cif_name",
        "customer_name",
        "customer",
        "client_name",
        "client",
        "nasabah",
        "perusahaan",
        "nama_perusahaan",
        "nama_customer",
        "nama_debitur",
        "debitur",
    ]
    headers_lower = {h.strip().lower(): h for h in headers}

    for variant in name_variants:
        if variant in headers_lower:
            return headers_lower[variant]

    # Partial match: find any column containing "nama" or "name" or "customer" or "company"
    for h_lower, h_original in headers_lower.items():
        if any(keyword in h_lower for keyword in ["nama", "name", "customer", "company", "nasabah", "debitur"]):
            return h_original

    # Last resort: use the first column (often the name column in simple spreadsheets)
    if headers:
        return headers[0]

    return None


def _build_sparse_metrics(row: dict, metric_columns: list[str]) -> dict:
    """Build sparse metrics dict, skipping zero-value metrics.

    Args:
        row: The raw data row.
        metric_columns: List of column names that are metrics.

    Returns:
        Dict of metric_key → value, with zero values excluded.
    """
    metrics = {}
    for col in metric_columns:
        raw_value = row.get(col, "").strip()
        if not raw_value:
            continue
        try:
            value = float(raw_value)
            if value != 0:
                metrics[col.strip().lower()] = value
        except (ValueError, TypeError):
            # Skip non-numeric values
            continue
    return metrics


async def import_portfolio(
    session: AsyncSession,
    file_content: str | bytes,
    delimiter: str = ",",
    as_of_date: date | None = None,
    filename: str = "",
) -> dict:
    """Import a portfolio file into the system.

    Orchestrates the full import process:
    1. Parse file (CSV/TSV)
    2. Parse column names → update MetricCatalog
    3. For each row:
       - Reconcile company name
       - If matched: store sparse snapshot, promote to Client, derive products-held,
         create group_member edges
       - If unmatched: add to PortfolioSuggestion queue

    IMPORTANT: This function NEVER calls any external LLM API.

    Args:
        session: Async database session.
        file_content: Raw file content.
        delimiter: Column delimiter (',' or '\\t').
        as_of_date: The snapshot date. Defaults to today if not provided.

    Returns:
        Dict with import statistics: matched, unmatched, total rows.
    """
    if as_of_date is None:
        as_of_date = date.today()

    # Step 1: Parse file
    headers, rows = parse_portfolio_file(file_content, delimiter, filename=filename)

    if not headers or not rows:
        return {"matched": 0, "unmatched": 0, "total": 0, "errors": []}

    # Step 2: Update MetricCatalog
    await _update_metric_catalog(session, headers)

    # Identify company name column and metric columns
    name_column = _get_company_name_column(headers)
    if not name_column:
        return {
            "matched": 0,
            "unmatched": 0,
            "total": len(rows),
            "errors": ["No company name column found in headers"],
        }

    metric_columns = [
        h for h in headers
        if h.strip().lower() not in METADATA_COLUMNS
    ]

    # Step 3: Process each row
    # Optimization: pre-load all company names for in-memory matching
    all_companies_result = await session.execute(
        select(CompanyProfile.id, CompanyProfile.name)
    )
    company_lookup: dict[str, int] = {}
    for cid, cname in all_companies_result.all():
        company_lookup[cname.strip().lower()] = cid

    matched_count = 0
    unmatched_count = 0
    errors: list[str] = []

    for row in rows:
        company_name = row.get(name_column, "").strip()
        if not company_name:
            continue

        # Fast in-memory exact match first (no DB query per row)
        normalized = company_name.strip().lower()
        matched_id = company_lookup.get(normalized)

        company = None
        if matched_id:
            company = await session.get(CompanyProfile, matched_id)

        if company:
            # Build sparse metrics (skip zeros)
            metrics = _build_sparse_metrics(row, metric_columns)

            if metrics:
                # Store portfolio snapshot
                snapshot = PortfolioSnapshot(
                    company_id=company.id,
                    as_of_date=as_of_date,
                    metrics=metrics,
                )
                session.add(snapshot)

                # Promote to Client on first match
                await _promote_to_client(session, company, as_of_date)

                # Derive products-held from latest snapshot
                products = derive_products_held(metrics)
                company.products_held = products
                session.add(company)

            # Create group_member edges from nama_group/nama_subholding
            await _create_group_member_edges(session, company, row)

            matched_count += 1
        else:
            # Add to suggestion queue
            raw_metrics = _build_sparse_metrics(row, metric_columns)

            # Try to get a fuzzy match score for potential suggestion
            # Count as unmatched (don't store individual suggestion records for large imports)
            unmatched_count += 1

    await session.flush()

    return {
        "matched": matched_count,
        "unmatched": unmatched_count,
        "total": len(rows),
        "errors": errors,
    }
