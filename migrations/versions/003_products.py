"""
Products schema migration.

Revision ID: 003_products
Revises: 002_categories_attributes
Create Date: 2026-08-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_products'
down_revision: Union[str, None] = '002_categories_attributes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Suppliers
    op.create_table('suppliers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('config_json', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )

    # Suppliers categories
    op.create_table('supplier_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('supplier_name', sa.String(length=500), nullable=False),
        sa.Column('is_removed', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_supplier_categories_supplier_id'), 'supplier_categories', ['supplier_id'], unique=False)
    op.create_index(op.f('ix_supplier_categories_supplier_name'), 'supplier_categories', ['supplier_name'], unique=False)

    # Suppliers attributes
    op.create_table('supplier_attributes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=False),
        sa.Column('supplier_name', sa.String(length=500), nullable=False),
        sa.Column('is_removed', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_supplier_attributes_supplier_id'), 'supplier_attributes', ['supplier_id'], unique=False)
    op.create_index(op.f('ix_supplier_attributes_supplier_name'), 'supplier_attributes', ['supplier_name'], unique=False)

    # Supplier attribute values
    op.create_table('supplier_attribute_values',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('supplier_attribute_id', sa.Integer(), nullable=False),
        sa.Column('supplier_value', sa.String(length=500), nullable=False),
        sa.Column('is_removed', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['supplier_attribute_id'], ['supplier_attributes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_supplier_attribute_values_supplier_attribute_id'), 'supplier_attribute_values', ['supplier_attribute_id'], unique=False)
    op.create_index(op.f('ix_supplier_attribute_values_supplier_value'), 'supplier_attribute_values', ['supplier_value'], unique=False)

    # Products
    op.create_table('products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('legacy_id', sa.Integer(), nullable=True),
        sa.Column('supplier_id', sa.Integer(), nullable=True),
        sa.Column('supplier_sku', sa.String(length=255), nullable=True),
        sa.Column('sku', sa.String(length=255), nullable=True),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('slug', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('short_description', sa.Text(), nullable=True),
        sa.Column('brand_id', sa.Integer(), nullable=True),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.Column('old_price', sa.Integer(), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('stock_status', sa.String(length=50), nullable=False),
        sa.Column('stock_qty', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_visible', sa.Boolean(), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'PUBLISHED', 'HIDDEN', 'ARCHIVED', name='productstatus'), nullable=False),
        sa.Column('meta_json', sa.Text(), nullable=True),
        sa.Column('search_vector', sa.Text(), nullable=True),
        sa.Column('imported_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['brand_id'], ['brands.id'], ),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
        sa.UniqueConstraint('supplier_id', 'supplier_sku')
    )
    op.create_index(op.f('ix_products_legacy_id'), 'products', ['legacy_id'], unique=False)
    op.create_index(op.f('ix_products_sku'), 'products', ['sku'], unique=False)
    op.create_index(op.f('ix_products_slug'), 'products', ['slug'], unique=False)
    op.create_index(op.f('ix_products_supplier_sku'), 'products', ['supplier_sku'], unique=False)

    # Product images
    op.create_table('product_images',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(length=1000), nullable=False),
        sa.Column('path', sa.String(length=500), nullable=True),
        sa.Column('alt', sa.String(length=255), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False),
        sa.Column('checksum', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_product_images_product_id'), 'product_images', ['product_id'], unique=False)

    # Product categories
    op.create_table('product_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'category_id')
    )
    op.create_index(op.f('ix_product_categories_category_id'), 'product_categories', ['category_id'], unique=False)
    op.create_index(op.f('ix_product_categories_product_id'), 'product_categories', ['product_id'], unique=False)

    # Product attributes
    op.create_table('product_attributes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('attribute_id', sa.Integer(), nullable=False),
        sa.Column('attribute_value_id', sa.Integer(), nullable=True),
        sa.Column('value_text', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['attribute_id'], ['attributes.id'], ),
        sa.ForeignKeyConstraint(['attribute_value_id'], ['attribute_values.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'attribute_id')
    )
    op.create_index(op.f('ix_product_attributes_attribute_id'), 'product_attributes', ['attribute_id'], unique=False)
    op.create_index(op.f('ix_product_attributes_attribute_value_id'), 'product_attributes', ['attribute_value_id'], unique=False)
    op.create_index(op.f('ix_product_attributes_product_id'), 'product_attributes', ['product_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_product_attributes_product_id'), table_name='product_attributes')
    op.drop_index(op.f('ix_product_attributes_attribute_value_id'), table_name='product_attributes')
    op.drop_index(op.f('ix_product_attributes_attribute_id'), table_name='product_attributes')
    op.drop_table('product_attributes')
    op.drop_index(op.f('ix_product_categories_product_id'), table_name='product_categories')
    op.drop_index(op.f('ix_product_categories_category_id'), table_name='product_categories')
    op.drop_table('product_categories')
    op.drop_index(op.f('ix_product_images_product_id'), table_name='product_images')
    op.drop_table('product_images')
    op.drop_index(op.f('ix_products_supplier_sku'), table_name='products')
    op.drop_index(op.f('ix_products_slug'), table_name='products')
    op.drop_index(op.f('ix_products_sku'), table_name='products')
    op.drop_index(op.f('ix_products_legacy_id'), table_name='products')
    op.drop_table('products')
    op.drop_index(op.f('ix_supplier_attribute_values_supplier_value'), table_name='supplier_attribute_values')
    op.drop_index(op.f('ix_supplier_attribute_values_supplier_attribute_id'), table_name='supplier_attribute_values')
    op.drop_table('supplier_attribute_values')
    op.drop_index(op.f('ix_supplier_attributes_supplier_name'), table_name='supplier_attributes')
    op.drop_index(op.f('ix_supplier_attributes_supplier_id'), table_name='supplier_attributes')
    op.drop_table('supplier_attributes')
    op.drop_index(op.f('ix_supplier_categories_supplier_name'), table_name='supplier_categories')
    op.drop_index(op.f('ix_supplier_categories_supplier_id'), table_name='supplier_categories')
    op.drop_table('supplier_categories')
    op.drop_table('suppliers')
