"""Charts and analytics Pydantic schemas.

Defines response models for score history and workspace analytics
endpoints, supporting frontend chart rendering.
"""

from datetime import datetime

from pydantic import BaseModel


class ScoreHistoryItem(BaseModel):
    """Single point-in-time score snapshot for a company."""

    overall_score: float | None = None
    financial_health: float | None = None
    business_risk: float | None = None
    growth_potential: float | None = None
    product_fit: float | None = None
    relationship_accessibility: float | None = None
    scored_at: datetime


class ScoreHistoryResponse(BaseModel):
    """Score history for a company across all snapshots."""

    company_id: int
    company_name: str
    history: list[ScoreHistoryItem]


class CompanyScores(BaseModel):
    """Current scores for a company within a workspace (for grouped bar/radar charts)."""

    id: int
    name: str
    overall_score: float | None = None
    financial_health: float | None = None
    business_risk: float | None = None
    growth_potential: float | None = None
    product_fit: float | None = None
    relationship_accessibility: float | None = None


class LeaderboardEntry(BaseModel):
    """Ranked company entry for the leaderboard display."""

    rank: int
    id: int
    name: str
    overall_score: float | None = None


class WorkspaceAnalyticsResponse(BaseModel):
    """Workspace-level analytics data for comparison charts and leaderboard."""

    workspace_id: int
    companies: list[CompanyScores]
    leaderboard: list[LeaderboardEntry]
