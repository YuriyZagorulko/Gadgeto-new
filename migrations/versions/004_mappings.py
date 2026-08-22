"""
Mappings schema migration.

Revision ID: 004_mappings
Revises: 003_products
Create Date: 2026-08-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004_mappings'
down_revision: Union[str, None] = '003_products'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Category mappings
    op.create_table('category_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('supplier_category_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['supplier_category_id'], ['supplier_categories.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_category_mappings_supplier_category_id'), 'category_mappings', ['supplier_category_id'], unique=False)

    # Attribute mappings
    op.create_table('attribute_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('supplier_attribute_id', sa.Integer(), nullable=False),
        sa.Column('attribute_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['attribute_id'], ['attributes.id'], ),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['supplier_attribute_id'], ['supplier_attributes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attribute_mappings_supplier_attribute_id'), 'attribute_mappings', ['supplier_attribute_id'], unique=False)

    # Attribute value mappings
    op.create_table('attribute_value_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('supplier_attribute_value_id', sa.Integer(), nullable=False),
        sa.Column('attribute_value_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['attribute_value_id'], ['attribute_values.id'], ),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['supplier_attribute_value_id'], ['supplier_attribute_values.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attribute_value_mappings_supplier_attribute_value_id'), 'attribute_value_mappings', ['supplier_attribute_value_id'], unique=False)

    # Mapping sources (archived JSON files)
    op.create_table('mapping_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('archived_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sha256')
    )
    op.create_index(op.f('ix_mapping_sources_file_name'), 'mapping_sources', ['file_name'], unique=False)

    # Supplier products (ledger for idempotent imports)
    op.create_table('supplier_products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=False),
        sa.Column('supplier_sku', sa.String(length=255), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('raw_json', sa.Text(), nullable=True),
        sa.Column('last_price', sa.Integer(), nullable=True),
        sa.Column('last_stock', sa.Integer(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('is_removed_from_feed', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('supplier_id', 'supplier_sku')
    )
    op.create_index(op.f('ix_supplier_products_supplier_id'), 'supplier_products', ['supplier_id'], unique=False)
    op.create_index(op.f('ix_supplier_products_supplier_sku'), 'supplier_products', ['supplier_sku'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_supplier_products_supplier_sku'), table_name='supplier_products')
    op.drop_index(op.f('ix_supplier_products_supplier_id'), table_name='supplier_products')
    op.drop_table('supplier_products')
    op.drop_index(op.f('ix_mapping_sources_file_name'), table_name='mapping_sources')
    op.drop_table('mapping_sources')
    op.drop_index(op.f('ix_attribute_value_mappings_supplier_attribute_value_id'), table_name='attribute_value_mappings')
    op.drop_table('attribute_value_mappings')
    op.drop_index(op.f('ix_attribute_mappings_supplier_attribute_id'), table_name='attribute_mappings')
    op.drop_table('attribute_mappings')
    op.drop_index(op.f('ix_category_mappings_supplier_category_id'), table_name='category_mappings')
    op.drop_table('category_mappings')
