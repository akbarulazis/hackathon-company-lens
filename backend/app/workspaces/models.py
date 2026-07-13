"""Workspace database models.

Defines Workspace, WorkspaceCompany association, and ComparisonReport tables.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Workspace(Base):
    """User workspace containing a set of companies for analysis."""

    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_limit: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="workspaces")  # noqa: F821
    workspace_companies: Mapped[list["WorkspaceCompany"]] = relationship(
        back_populates="workspace"
    )
    comparison_reports: Mapped[list["ComparisonReport"]] = relationship(
        back_populates="workspace"
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(  # noqa: F821
        back_populates="workspace"
    )

    def __repr__(self) -> str:
        return f"<Workspace(id={self.id}, name={self.name!r}, user_id={self.user_id})>"


class WorkspaceCompany(Base):
    """Association between workspaces and companies."""

    __tablename__ = "workspace_companies"

    workspace_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("company_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="workspace_companies")
    company: Mapped["CompanyProfile"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<WorkspaceCompany(workspace_id={self.workspace_id}, "
            f"company_id={self.company_id})>"
        )


class ComparisonReport(Base):
    """AI-generated comparison report for companies in a workspace."""

    __tablename__ = "comparison_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    company_ids: Mapped[dict] = mapped_column(JSONB, nullable=False)
    html_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="comparison_reports")

    def __repr__(self) -> str:
        return f"<ComparisonReport(id={self.id}, workspace_id={self.workspace_id})>"
