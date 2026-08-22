"""
Orders and payments schema migration.

Revision ID: 005_orders_payments
Revises: 004_mappings
Create Date: 2026-08-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005_orders_payments'
down_revision: Union[str, None] = '004_mappings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Brands
    op.create_table('brands',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('logo', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_brands_slug'), 'brands', ['slug'], unique=False)

    # Orders
    op.create_table('orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('number', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('buyer_name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'PAID', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'REFUNDED', name='orderstatus'), nullable=False),
        sa.Column('total_amount', sa.Integer(), nullable=False),
        sa.Column('subtotal_amount', sa.Integer(), nullable=False),
        sa.Column('shipping_amount', sa.Integer(), nullable=False),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column('payment_status', sa.String(length=50), nullable=False),
        sa.Column('shipping_address_json', sa.Text(), nullable=True),
        sa.Column('city_ref', sa.String(length=255), nullable=True),
        sa.Column('warehouse_ref', sa.String(length=255), nullable=True),
        sa.Column('warehouse_number', sa.String(length=50), nullable=True),
        sa.Column('area_name', sa.String(length=255), nullable=True),
        sa.Column('delivery_address', sa.String(length=500), nullable=True),
        sa.Column('recipient_name', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('number')
    )
    op.create_index(op.f('ix_orders_user_id'), 'orders', ['user_id'], unique=False)

    # Order items
    op.create_table('order_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('product_name', sa.String(length=500), nullable=False),
        sa.Column('product_sku', sa.String(length=255), nullable=True),
        sa.Column('qty', sa.Integer(), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.Column('total', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_items_order_id'), 'order_items', ['order_id'], unique=False)
    op.create_index(op.f('ix_order_items_product_id'), 'order_items', ['product_id'], unique=False)

    # Order events
    op.create_table('order_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('event', sa.String(length=100), nullable=False),
        sa.Column('actor', sa.String(length=50), nullable=True),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_order_events_order_id'), 'order_events', ['order_id'], unique=False)

    # Payments
    op.create_table('payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('payment_id', sa.String(length=255), nullable=False),
        sa.Column('liqpay_order_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('card_mask', sa.String(length=20), nullable=True),
        sa.Column('card_type', sa.String(length=50), nullable=True),
        sa.Column('raw_callback_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('payment_id')
    )
    op.create_index(op.f('ix_payments_order_id'), 'payments', ['order_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_payments_order_id'), table_name='payments')
    op.drop_table('payments')
    op.drop_index(op.f('ix_order_events_order_id'), table_name='order_events')
    op.drop_table('order_events')
    op.drop_index(op.f('ix_order_items_product_id'), table_name='order_items')
    op.drop_index(op.f('ix_order_items_order_id'), table_name='order_items')
    op.drop_table('order_items')
    op.drop_index(op.f('ix_orders_user_id'), table_name='orders')
    op.drop_table('orders')
    op.drop_index(op.f('ix_brands_slug'), table_name='brands')
    op.drop_table('brands')
