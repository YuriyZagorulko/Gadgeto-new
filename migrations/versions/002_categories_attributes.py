"""
Categories and attributes schema migration.

Revision ID: 002_categories_attributes
Revises: 001_initial_schema
Create Date: 2026-08-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_categories_attributes'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Categories
    op.create_table('categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('legacy_id', sa.Integer(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('seo_title', sa.String(length=255), nullable=True),
        sa.Column('seo_description', sa.Text(), nullable=True),
        sa.Column('seo_focus_keyphrase', sa.String(length=255), nullable=True),
        sa.Column('image', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['parent_id'], ['categories.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_categories_legacy_id'), 'categories', ['legacy_id'], unique=False)
    op.create_index(op.f('ix_categories_slug'), 'categories', ['slug'], unique=False)

    # Category closure for tree queries
    op.create_table('category_closure',
        sa.Column('ancestor_id', sa.Integer(), nullable=False),
        sa.Column('descendant_id', sa.Integer(), nullable=False),
        sa.Column('path_length', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['ancestor_id'], ['categories.id'], ),
        sa.ForeignKeyConstraint(['descendant_id'], ['categories.id'], ),
        sa.PrimaryKeyConstraint('ancestor_id', 'descendant_id')
    )

    # Attributes
    op.create_table('attributes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('is_global', sa.Boolean(), nullable=False),
        sa.Column('is_filterable', sa.Boolean(), nullable=False),
        sa.Column('legacy_value_set', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_attributes_slug'), 'attributes', ['slug'], unique=False)

    op.create_table('attribute_values',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('attribute_id', sa.Integer(), nullable=False),
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('sort', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['attribute_id'], ['attributes.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('attribute_id', 'value')
    )
    op.create_index(op.f('ix_attribute_values_slug'), 'attribute_values', ['slug'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_attribute_values_slug'), table_name='attribute_values')
    op.drop_table('attribute_values')
    op.drop_index(op.f('ix_attributes_slug'), table_name='attributes')
    op.drop_table('attributes')
    op.drop_table('category_closure')
    op.drop_index(op.f('ix_categories_slug'), table_name='categories')
    op.drop_index(op.f('ix_categories_legacy_id'), table_name='categories')
    op.drop_table('categories')
