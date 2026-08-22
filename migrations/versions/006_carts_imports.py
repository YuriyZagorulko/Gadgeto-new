"""
Carts and imports schema migration.

Revision ID: 006_carts_imports
Revises: 005_orders_payments
Create Date: 2026-08-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '006_carts_imports'
down_revision: Union[str, None] = '005_orders_payments'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Carts
    op.create_table('carts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_token', sa.String(length=64), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_carts_session_token'), 'carts', ['session_token'], unique=False)
    op.create_index(op.f('ix_carts_user_id'), 'carts', ['user_id'], unique=False)

    # Cart items
    op.create_table('cart_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cart_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('qty', sa.Integer(), nullable=False),
        sa.Column('price_at_addition', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['cart_id'], ['carts.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cart_id', 'product_id')
    )
    op.create_index(op.f('ix_cart_items_cart_id'), 'cart_items', ['cart_id'], unique=False)
    op.create_index(op.f('ix_cart_items_product_id'), 'cart_items', ['product_id'], unique=False)

    # Import jobs
    op.create_table('import_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=False),
        sa.Column('import_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.Enum('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'ABORTED', name='importjobstatus'), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('stats_json', sa.Text(), nullable=True),
        sa.Column('error_details_json', sa.Text(), nullable=True),
        sa.Column('triggered_by_user_id', sa.Integer(), nullable=True),
        sa.Column('raw_config_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
        sa.ForeignKeyConstraint(['triggered_by_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_import_jobs_supplier_id'), 'import_jobs', ['supplier_id'], unique=False)

    # Import logs
    op.create_table('import_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('level', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('item_ref', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['import_jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_import_logs_job_id'), 'import_logs', ['job_id'], unique=False)

    # Category filters
    op.create_table('category_filters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('attribute_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['attribute_id'], ['attributes.id'], ),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category_id', 'attribute_id')
    )
    op.create_index(op.f('ix_category_filters_attribute_id'), 'category_filters', ['attribute_id'], unique=False)
    op.create_index(op.f('ix_category_filters_category_id'), 'category_filters', ['category_id'], unique=False)

    # Settings
    op.create_table('settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('is_secret', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )

    # URL aliases
    op.create_table('url_aliases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('old_url', sa.String(length=500), nullable=False),
        sa.Column('new_url', sa.String(length=500), nullable=False),
        sa.Column('http_status', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_url_aliases_old_url'), 'url_aliases', ['old_url'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_url_aliases_old_url'), table_name='url_aliases')
    op.drop_table('url_aliases')
    op.drop_table('settings')
    op.drop_index(op.f('ix_category_filters_category_id'), table_name='category_filters')
    op.drop_index(op.f('ix_category_filters_attribute_id'), table_name='category_filters')
    op.drop_table('category_filters')
    op.drop_index(op.f('ix_import_logs_job_id'), table_name='import_logs')
    op.drop_table('import_logs')
    op.drop_index(op.f('ix_import_jobs_supplier_id'), table_name='import_jobs')
    op.drop_table('import_jobs')
    op.drop_index(op.f('ix_cart_items_product_id'), table_name='cart_items')
    op.drop_index(op.f('ix_cart_items_cart_id'), table_name='cart_items')
    op.drop_table('cart_items')
    op.drop_index(op.f('ix_carts_user_id'), table_name='carts')
    op.drop_index(op.f('ix_carts_session_token'), table_name='carts')
    op.drop_table('carts')
