"""Company database models.

Defines CompanyProfile, ScoreSnapshot, CompanyRelationship tables
and related enums: CompanyStatus, ClientStatus, RelationType.
"""

import enum
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CompanyStatus(str, enum.Enum):
    """Pipeline status for company research."""

    pending = "pending"
    researching = "researching"
    profiling = "profiling"
    scoring = "scoring"
    ready = "ready"
    failed = "failed"


class ClientStatus(str, enum.Enum):
    """Client relationship status."""

    client = "client"
    prospect = "prospect"
    unknown = "unknown"


class RelationType(str, enum.Enum):
    """Types of relationships between companies."""

    parent = "parent"
    subsidiary = "subsidiary"
    vendor = "vendor"
    customer = "customer"
    partner = "partner"
    group_member = "group_member"


class CompanyProfile(Base):
    """Central company entity with research data and scores."""

    __tablename__ = "company_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CompanyStatus] = mapped_column(
        Enum(CompanyStatus, name="company_status"),
        default=CompanyStatus.pending,
        nullable=False,
    )
    client_status: Mapped[ClientStatus] = mapped_column(
        Enum(ClientStatus, name="client_status"),
        default=ClientStatus.unknown,
        nullable=False,
    )
    acquisition_brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    headquarters: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_revenue: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    funding_total: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    company_website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ticker: Mapped[str | None] = mapped_column(String(20), nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    financial_health: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    business_risk: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    growth_potential: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    product_fit: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    relationship_accessibility: Mapped[float | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    # Score insights (AI-generated reasoning)
    financial_health_insight: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_risk_insight: Mapped[str | None] = mapped_column(Text, nullable=True)
    growth_potential_insight: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_fit_insight: Mapped[str | None] = mapped_column(Text, nullable=True)
    relationship_accessibility_insight: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_insight: Mapped[str | None] = mapped_column(Text, nullable=True)
    revenue_projection: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    client_since: Mapped[date | None] = mapped_column(Date, nullable=True)
    products_held: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    score_snapshots: Mapped[list["ScoreSnapshot"]] = relationship(back_populates="company")
    text_chunks: Mapped[list["TextChunk"]] = relationship(back_populates="company")  # noqa: F821
    documents: Mapped[list["Document"]] = relationship(back_populates="company")  # noqa: F821
    portfolio_snapshots: Mapped[list["PortfolioSnapshot"]] = relationship(  # noqa: F821
        back_populates="company"
    )
    relationships_as_source: Mapped[list["CompanyRelationship"]] = relationship(
        back_populates="source", foreign_keys="CompanyRelationship.source_id"
    )
    relationships_as_target: Mapped[list["CompanyRelationship"]] = relationship(
        back_populates="target", foreign_keys="CompanyRelationship.target_id"
    )

    def __repr__(self) -> str:
        return f"<CompanyProfile(id={self.id}, name={self.name!r}, status={self.status.value!r})>"


class ScoreSnapshot(Base):
    """Point-in-time snapshot of company scores."""

    __tablename__ = "score_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_profiles.id", ondelete="CASCADE"), nullable=False
    )
    overall_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    financial_health: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    business_risk: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    growth_potential: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    product_fit: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    relationship_accessibility: Mapped[float | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    company: Mapped["CompanyProfile"] = relationship(back_populates="score_snapshots")

    def __repr__(self) -> str:
        return (
            f"<ScoreSnapshot(id={self.id}, company_id={self.company_id}, "
            f"overall={self.overall_score})>"
        )


class CompanyRelationship(Base):
    """Directed relationship edge between two companies."""

    __tablename__ = "company_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_profiles.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_profiles.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[RelationType] = mapped_column(
        Enum(RelationType, name="relation_type"), nullable=False
    )
    origin: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    source: Mapped["CompanyProfile"] = relationship(
        back_populates="relationships_as_source", foreign_keys=[source_id]
    )
    target: Mapped["CompanyProfile"] = relationship(
        back_populates="relationships_as_target", foreign_keys=[target_id]
    )

    def __repr__(self) -> str:
        return (
            f"<CompanyRelationship(id={self.id}, {self.source_id} "
            f"-[{self.relation_type.value}]-> {self.target_id})>"
        )
