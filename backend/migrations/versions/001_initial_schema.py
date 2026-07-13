"""Initial schema with all tables and indexes.

Revision ID: 001
Revises: None
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable required PostgreSQL extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- Users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(150), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- Refresh Tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), default=False, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- Login Attempts ---
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(150), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- Company Profiles ---
    op.create_table(
        "company_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "researching", "profiling", "scoring", "ready", "failed",
                name="company_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "client_status",
            sa.Enum("client", "prospect", "unknown", name="client_status"),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("acquisition_brief", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(255), nullable=True),
        sa.Column("founded_year", sa.Integer(), nullable=True),
        sa.Column("headquarters", sa.String(255), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("annual_revenue", sa.Numeric(18, 2), nullable=True),
        sa.Column("funding_total", sa.Numeric(18, 2), nullable=True),
        sa.Column("market_cap", sa.Numeric(18, 2), nullable=True),
        sa.Column("company_website", sa.String(500), nullable=True),
        sa.Column("linkedin_url", sa.String(500), nullable=True),
        sa.Column("ticker", sa.String(20), nullable=True),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("financial_health", sa.Numeric(5, 2), nullable=True),
        sa.Column("business_risk", sa.Numeric(5, 2), nullable=True),
        sa.Column("growth_potential", sa.Numeric(5, 2), nullable=True),
        sa.Column("product_fit", sa.Numeric(5, 2), nullable=True),
        sa.Column("relationship_accessibility", sa.Numeric(5, 2), nullable=True),
        sa.Column("client_since", sa.Date(), nullable=True),
        sa.Column("products_held", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- Score Snapshots ---
    op.create_table(
        "score_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("company_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("financial_health", sa.Numeric(5, 2), nullable=True),
        sa.Column("business_risk", sa.Numeric(5, 2), nullable=True),
        sa.Column("growth_potential", sa.Numeric(5, 2), nullable=True),
        sa.Column("product_fit", sa.Numeric(5, 2), nullable=True),
        sa.Column("relationship_accessibility", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "scored_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- Workspaces ---
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("company_limit", sa.Integer(), nullable=False, server_default="3"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- Workspace Companies (association) ---
    op.create_table(
        "workspace_companies",
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("company_profiles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- Comparison Reports ---
    op.create_table(
        "comparison_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_ids", JSONB(), nullable=False),
        sa.Column("html_content", sa.Text(), nullable=True),
        sa.Column("is_fallback", sa.Boolean(), default=False, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- Chat Messages ---
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- Documents ---
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("company_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("key_points", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- Text Chunks (with pgvector) ---
    op.create_table(
        "text_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("company_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Add pgvector column via raw SQL for proper vector type
    op.execute("ALTER TABLE text_chunks ADD COLUMN embedding vector(1536)")

    # --- Company Relationships ---
    op.create_table(
        "company_relationships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("company_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            sa.Integer(),
            sa.ForeignKey("company_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "relation_type",
            sa.Enum(
                "parent", "subsidiary", "vendor", "customer", "partner", "group_member",
                name="relation_type",
            ),
            nullable=False,
        ),
        sa.Column("origin", sa.String(100), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- Portfolio Snapshots ---
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("company_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("metrics", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- Metric Catalog ---
    op.create_table(
        "metric_catalog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("column_name", sa.String(255), unique=True, nullable=False),
        sa.Column("division", sa.String(255), nullable=True),
        sa.Column("product_group", sa.String(255), nullable=True),
        sa.Column("subproduct", sa.String(255), nullable=True),
        sa.Column("metric", sa.String(255), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("reviewed", sa.Boolean(), default=False, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- Portfolio Suggestions ---
    op.create_table(
        "portfolio_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("raw_name", sa.String(500), nullable=False),
        sa.Column(
            "matched_company_id",
            sa.Integer(),
            sa.ForeignKey("company_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("as_of_date", sa.Date(), nullable=True),
        sa.Column("raw_metrics", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ===== INDEXES =====

    # pg_trgm GIN index for fuzzy company name search
    op.execute(
        "CREATE INDEX idx_company_name_trgm ON company_profiles "
        "USING gin (name gin_trgm_ops)"
    )

    # pgvector IVFFlat index for embedding similarity search
    op.execute(
        "CREATE INDEX idx_text_chunks_embedding ON text_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    # Composite indexes
    op.create_index(
        "idx_workspace_company",
        "workspace_companies",
        ["workspace_id", "company_id"],
    )
    op.create_index(
        "idx_text_chunks_company",
        "text_chunks",
        ["company_id"],
    )
    op.create_index(
        "idx_text_chunks_workspace",
        "text_chunks",
        ["workspace_id"],
    )
    op.execute(
        "CREATE INDEX idx_score_snapshots_company ON score_snapshots (company_id, scored_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_portfolio_snapshots_company "
        "ON portfolio_snapshots (company_id, as_of_date DESC)"
    )
    op.create_index(
        "idx_company_relationships_source",
        "company_relationships",
        ["source_id"],
    )
    op.create_index(
        "idx_company_relationships_target",
        "company_relationships",
        ["target_id"],
    )
    op.execute(
        "CREATE INDEX idx_login_attempts ON login_attempts (username, attempted_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_chat_messages_workspace ON chat_messages (workspace_id, created_at DESC)"
    )


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_chat_messages_workspace")
    op.execute("DROP INDEX IF EXISTS idx_login_attempts")
    op.drop_index("idx_company_relationships_target")
    op.drop_index("idx_company_relationships_source")
    op.execute("DROP INDEX IF EXISTS idx_portfolio_snapshots_company")
    op.execute("DROP INDEX IF EXISTS idx_score_snapshots_company")
    op.drop_index("idx_text_chunks_workspace")
    op.drop_index("idx_text_chunks_company")
    op.drop_index("idx_workspace_company")
    op.execute("DROP INDEX IF EXISTS idx_text_chunks_embedding")
    op.execute("DROP INDEX IF EXISTS idx_company_name_trgm")

    # Drop tables in reverse dependency order
    op.drop_table("portfolio_suggestions")
    op.drop_table("metric_catalog")
    op.drop_table("portfolio_snapshots")
    op.drop_table("company_relationships")
    op.drop_table("text_chunks")
    op.drop_table("documents")
    op.drop_table("chat_messages")
    op.drop_table("comparison_reports")
    op.drop_table("workspace_companies")
    op.drop_table("workspaces")
    op.drop_table("score_snapshots")
    op.drop_table("company_profiles")
    op.drop_table("login_attempts")
    op.drop_table("refresh_tokens")
    op.drop_table("users")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS relation_type")
    op.execute("DROP TYPE IF EXISTS client_status")
    op.execute("DROP TYPE IF EXISTS company_status")

    # Drop extensions (optional, may be used by other schemas)
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
