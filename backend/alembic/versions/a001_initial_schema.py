"""Initial schema - projects, experiments, trials tables.

Revision ID: 001_initial
Revises:
Create Date: 2024-02-06

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Projects table
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(512), nullable=False, server_default=""),
        sa.Column("filename", sa.String(512), nullable=False, server_default=""),
        sa.Column("upload_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("input_video_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("output_dir", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_type", sa.String(64), nullable=False, server_default="general"),
        sa.Column("config", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("metadata", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="uploaded"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_stage", sa.String(128), nullable=False, server_default=""),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("output_paths", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("engagement_prediction", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("chapters", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("multi_kills", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("clutch_moments", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_created_at", "projects", ["created_at"])

    # Experiments table
    op.create_table(
        "experiments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_type", sa.String(64), nullable=False, server_default="general"),
        sa.Column("parameter_space", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="created"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_experiments_status", "experiments", ["status"])

    # Trials table
    op.create_table(
        "trials",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "experiment_id",
            sa.String(36),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trial_num", sa.Integer(), nullable=False),
        sa.Column("parameters", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("reward_total", sa.Float(), nullable=True),
        sa.Column("reward_components", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("reward_weights", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("sub_metrics", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_trials_experiment_id", "trials", ["experiment_id"])


def downgrade() -> None:
    op.drop_table("trials")
    op.drop_table("experiments")
    op.drop_table("projects")
