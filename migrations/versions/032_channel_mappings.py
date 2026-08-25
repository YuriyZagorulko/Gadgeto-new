"""032: Channel (Rozetka) mapping tables — Internal → External.

Three mapping kinds matching the three existing channel_external taxonomy
tables:
  channel_category_mappings  — Internal Category → External Channel Category
  channel_attribute_mappings — Internal Attribute → External Channel Attribute
  channel_value_mappings     — Internal Value → External Channel Value

Direction is strictly Internal → Channel.  The existing supplier mapping
tables (category_mappings, attribute_mappings, attribute_value_mappings)
are NOT reused.

Each mapping has status (proposed / accepted / excluded), confidence
(float 0-1) and source (manual / auto) for the suggestion engine.

Attribute and value mappings optionally carry external_category_id because
Rozetka characteristics are category-scoped.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "032_channel_mappings"
down_revision: str = "031_channel_external_taxonomy"


def upgrade() -> None:
    op.create_table(
        "channel_category_mappings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("internal_category_id", sa.Integer(), nullable=False),
        sa.Column("external_category_id", sa.String(length=255), nullable=True),
        sa.Column("external_category_name", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="proposed"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]),
        sa.ForeignKeyConstraint(["internal_category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id", "internal_category_id",
                            name="uq_channel_cat_mapping"),
    )
    op.create_index(op.f("ix_channel_cat_map_channel"), "channel_category_mappings",
                    ["channel_id"], unique=False)
    op.create_index(op.f("ix_channel_cat_map_internal"), "channel_category_mappings",
                    ["internal_category_id"], unique=False)

    # __PART_B__

    op.create_table(
        "channel_attribute_mappings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("internal_attribute_id", sa.Integer(), nullable=False),
        sa.Column("external_attribute_id", sa.String(length=255), nullable=True),
        sa.Column("external_attribute_name", sa.String(length=500), nullable=True),
        sa.Column("external_category_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="proposed"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]),
        sa.ForeignKeyConstraint(["internal_attribute_id"], ["attributes.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id", "internal_attribute_id", "external_category_id",
                            name="uq_channel_attr_mapping"),
    )
    op.create_index(op.f("ix_channel_attr_map_channel"), "channel_attribute_mappings",
                    ["channel_id"], unique=False)
    op.create_index(op.f("ix_channel_attr_map_internal"), "channel_attribute_mappings",
                    ["internal_attribute_id"], unique=False)
    op.create_index(op.f("ix_channel_attr_map_ext_cat"), "channel_attribute_mappings",
                    ["external_category_id"], unique=False)

    # __PART_C__

    op.create_table(
        "channel_value_mappings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("internal_value_id", sa.Integer(), nullable=False),
        sa.Column("external_value_id", sa.String(length=255), nullable=True),
        sa.Column("external_value_name", sa.String(length=500), nullable=True),
        sa.Column("external_category_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="proposed"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]),
        sa.ForeignKeyConstraint(["internal_value_id"], ["attribute_values.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id", "internal_value_id", "external_category_id",
                            name="uq_channel_val_mapping"),
    )
    op.create_index(op.f("ix_channel_val_map_channel"), "channel_value_mappings",
                    ["channel_id"], unique=False)
    op.create_index(op.f("ix_channel_val_map_internal"), "channel_value_mappings",
                    ["internal_value_id"], unique=False)
    op.create_index(op.f("ix_channel_val_map_ext_cat"), "channel_value_mappings",
                    ["external_category_id"], unique=False)


def downgrade() -> None:
    op.drop_table("channel_value_mappings")
    op.drop_table("channel_attribute_mappings")
    op.drop_table("channel_category_mappings")