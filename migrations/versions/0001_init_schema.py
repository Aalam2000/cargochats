"""init schema

Revision ID: 0001_init_schema
Revises:
Create Date: 2026-01-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_init_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("cargo1_company_id", sa.Integer(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_companies_cargo1_company_id", "companies", ["cargo1_company_id"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cargo1_user_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("cargo1_user_id", name="uq_users_cargo1_user_id"),
    )
    op.create_index("ix_users_cargo1_user_id", "users", ["cargo1_user_id"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=32), server_default=sa.text("'operator'"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("company_id", "user_id", name="uq_memberships_company_user"),
    )
    op.create_index("ix_memberships_company_id", "memberships", ["company_id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])

    op.create_table(
        "resources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("company_id", "code", name="uq_resources_company_code"),
    )
    op.create_index("ix_resources_company_id", "resources", ["company_id"])
    op.create_index("ix_resources_kind", "resources", ["kind"])

    op.create_table(
        "resource_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("resource_id", name="uq_resource_settings_resource"),
    )
    op.create_index("ix_resource_settings_resource_id", "resource_settings", ["resource_id"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("resource_id", "code", name="uq_sessions_resource_code"),
    )
    op.create_index("ix_sessions_resource_id", "sessions", ["resource_id"])

    op.create_table(
        "session_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("session_id", name="uq_session_settings_session"),
    )
    op.create_index("ix_session_settings_session_id", "session_settings", ["session_id"])

    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("company_id", "code", name="uq_clients_company_code"),
    )
    op.create_index("ix_clients_company_id", "clients", ["company_id"])

    op.create_table(
        "client_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("resource_id", "external_id", name="uq_client_identities_resource_external"),
    )
    op.create_index("ix_client_identities_client_id", "client_identities", ["client_id"])
    op.create_index("ix_client_identities_resource_id", "client_identities", ["resource_id"])
    op.create_index("ix_client_identities_external_id", "client_identities", ["external_id"])
    op.create_index("ix_client_identities_kind", "client_identities", ["kind"])

    op.create_table(
        "dialogs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'open'"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_dialogs_company_id", "dialogs", ["company_id"])
    op.create_index("ix_dialogs_client_id", "dialogs", ["client_id"])
    op.create_index("ix_dialogs_company_client", "dialogs", ["company_id", "client_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dialog_id", sa.Integer(), sa.ForeignKey("dialogs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_messages_dialog_id", "messages", ["dialog_id"])
    op.create_index("ix_messages_resource_id", "messages", ["resource_id"])
    op.create_index("ix_messages_session_id", "messages", ["session_id"])
    op.create_index("ix_messages_dialog_created", "messages", ["dialog_id", "created_at"])

    op.create_table(
        "policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("priority", sa.Integer(), server_default=sa.text("100"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_policies_company_id", "policies", ["company_id"])
    op.create_index("ix_policies_resource_id", "policies", ["resource_id"])
    op.create_index("ix_policies_session_id", "policies", ["session_id"])
    op.create_index("ix_policies_company_priority", "policies", ["company_id", "priority"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.String(length=16), server_default=sa.text("'info'"), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dialog_id", sa.Integer(), sa.ForeignKey("dialogs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_events_company_id", "events", ["company_id"])
    op.create_index("ix_events_kind", "events", ["kind"])
    op.create_index("ix_events_resource_id", "events", ["resource_id"])
    op.create_index("ix_events_session_id", "events", ["session_id"])
    op.create_index("ix_events_dialog_id", "events", ["dialog_id"])
    op.create_index("ix_events_message_id", "events", ["message_id"])
    op.create_index("ix_events_company_created", "events", ["company_id", "created_at"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("queue", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'new'"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("is_locked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_jobs_company_id", "jobs", ["company_id"])
    op.create_index("ix_jobs_queue", "jobs", ["queue"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_company_queue_status", "jobs", ["company_id", "queue", "status"])


def downgrade() -> None:
    op.drop_index("ix_jobs_company_queue_status", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_queue", table_name="jobs")
    op.drop_index("ix_jobs_company_id", table_name="jobs")
    op.drop_table("jobs")

    op.drop_index("ix_events_company_created", table_name="events")
    op.drop_index("ix_events_message_id", table_name="events")
    op.drop_index("ix_events_dialog_id", table_name="events")
    op.drop_index("ix_events_session_id", table_name="events")
    op.drop_index("ix_events_resource_id", table_name="events")
    op.drop_index("ix_events_kind", table_name="events")
    op.drop_index("ix_events_company_id", table_name="events")
    op.drop_table("events")

    op.drop_index("ix_policies_company_priority", table_name="policies")
    op.drop_index("ix_policies_session_id", table_name="policies")
    op.drop_index("ix_policies_resource_id", table_name="policies")
    op.drop_index("ix_policies_company_id", table_name="policies")
    op.drop_table("policies")

    op.drop_index("ix_messages_dialog_created", table_name="messages")
    op.drop_index("ix_messages_session_id", table_name="messages")
    op.drop_index("ix_messages_resource_id", table_name="messages")
    op.drop_index("ix_messages_dialog_id", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_dialogs_company_client", table_name="dialogs")
    op.drop_index("ix_dialogs_client_id", table_name="dialogs")
    op.drop_index("ix_dialogs_company_id", table_name="dialogs")
    op.drop_table("dialogs")

    op.drop_index("ix_client_identities_kind", table_name="client_identities")
    op.drop_index("ix_client_identities_external_id", table_name="client_identities")
    op.drop_index("ix_client_identities_resource_id", table_name="client_identities")
    op.drop_index("ix_client_identities_client_id", table_name="client_identities")
    op.drop_table("client_identities")

    op.drop_index("ix_clients_company_id", table_name="clients")
    op.drop_table("clients")

    op.drop_index("ix_session_settings_session_id", table_name="session_settings")
    op.drop_table("session_settings")

    op.drop_index("ix_sessions_resource_id", table_name="sessions")
    op.drop_table("sessions")

    op.drop_index("ix_resource_settings_resource_id", table_name="resource_settings")
    op.drop_table("resource_settings")

    op.drop_index("ix_resources_kind", table_name="resources")
    op.drop_index("ix_resources_company_id", table_name="resources")
    op.drop_table("resources")

    op.drop_index("ix_memberships_user_id", table_name="memberships")
    op.drop_index("ix_memberships_company_id", table_name="memberships")
    op.drop_table("memberships")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_cargo1_user_id", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_companies_cargo1_company_id", table_name="companies")
    op.drop_table("companies")
