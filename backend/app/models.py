"""Import all SQLAlchemy models to ensure proper mapper configuration.

Import order matters: models that are referenced by relationship()
in other models must be imported first to be in the registry.
"""

# 1. Models with no cross-module relationships first
from app.auth.models import LoginAttempt, RefreshToken, User  # noqa: F401
from app.portfolio.models import MetricCatalog, PortfolioSnapshot, PortfolioSuggestion  # noqa: F401
from app.chatbot.models import ChatMessage  # noqa: F401
from app.workspaces.models import ComparisonReport, Workspace, WorkspaceCompany  # noqa: F401
from app.documents.models import Document, TextChunk  # noqa: F401

# 2. Models with cross-module relationship() references last
from app.companies.models import (  # noqa: F401
    CompanyProfile,
    CompanyRelationship,
    ScoreSnapshot,
)
