"""031: Rozetka (channel) external taxonomy reference tables.

Stores a local copy of the marketplace category, attribute and permissible-value
dictionaries.  These are populated by a "Refresh Taxonomy" operation that calls
the official Seller API.

Attributes are category-scoped (Rozetka characteristic groups belong to a
specific category), so channel_external_attributes has a
category_external_id.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "031_channel_external_taxonomy"
down_revision: str = "030_channel_publication_foundation"


def upgrade() -> None:
    op.create_table(
        "channel_external_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("parent_external_id", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id", "external_id",
                            name="uq_channel_ext_category"),
    )
    op.create_index(op.f("ix_channel_ext_cat_channel"), "channel_external_categories",
                    ["channel_id"], unique=False)
    op.create_index(op.f("ix_channel_ext_cat_external_id"), "channel_external_categories",
                    ["external_id"], unique=False)
    op.create_index(op.f("ix_channel_ext_cat_parent"), "channel_external_categories",
                    ["parent_external_id"], unique=False)

    op.create_table(
        "channel_external_attributes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("category_external_id", sa.String(length=255), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("param_type", sa.String(length=50), nullable=True),
        sa.Column("is_required", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=100), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id", "category_external_id", "external_id",
                            name="uq_channel_ext_attribute"),
    )
    op.create_index(op.f("ix_channel_ext_attr_channel"), "channel_external_attributes",
                    ["channel_id"], unique=False)
    op.create_index(op.f("ix_channel_ext_attr_cat"), "channel_external_attributes",
                    ["category_external_id"], unique=False)
    op.create_index(op.f("ix_channel_ext_attr_external_id"), "channel_external_attributes",
                    ["external_id"], unique=False)

    op.create_table(
        "channel_external_values",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("attribute_external_id", sa.String(length=255), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id", "attribute_external_id", "value",
                            name="uq_channel_ext_value"),
    )
    op.create_index(op.f("ix_channel_ext_val_channel"), "channel_external_values",
                    ["channel_id"], unique=False)
    op.create_index(op.f("ix_channel_ext_val_attr"), "channel_external_values",
                    ["attribute_external_id"], unique=False)
    op.create_index(op.f("ix_channel_ext_val_external_id"), "channel_external_values",
                    ["external_id"], unique=False)


def downgrade() -> None:
    op.drop_table("channel_external_values")
    op.drop_table("channel_external_attributes")
    op.drop_table("channel_external_categories")