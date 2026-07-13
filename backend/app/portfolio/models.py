"""Portfolio database models.

Defines PortfolioSnapshot, MetricCatalog, and PortfolioSuggestion tables.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PortfolioSnapshot(Base):
    """Point-in-time portfolio metrics for a company."""

    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_profiles.id", ondelete="CASCADE"), nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    company: Mapped["CompanyProfile"] = relationship(  # noqa: F821
        back_populates="portfolio_snapshots"
    )

    def __repr__(self) -> str:
        return (
            f"<PortfolioSnapshot(id={self.id}, company_id={self.company_id}, "
            f"as_of_date={self.as_of_date})>"
        )


class MetricCatalog(Base):
    """Catalog of known portfolio metric definitions."""

    __tablename__ = "metric_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    column_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    division: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_group: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subproduct: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metric: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<MetricCatalog(id={self.id}, column_name={self.column_name!r})>"


class PortfolioSuggestion(Base):
    """Fuzzy-matched company suggestion from portfolio import."""

    __tablename__ = "portfolio_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_name: Mapped[str] = mapped_column(String(500), nullable=False)
    matched_company_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("company_profiles.id", ondelete="SET NULL"), nullable=True
    )
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    as_of_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    raw_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    matched_company: Mapped["CompanyProfile | None"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<PortfolioSuggestion(id={self.id}, raw_name={self.raw_name!r}, "
            f"status={self.status!r})>"
        )
