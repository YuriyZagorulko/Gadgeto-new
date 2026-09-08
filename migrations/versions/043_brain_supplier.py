"""043: Seed BRAIN as the third fixed system supplier.

Suppliers are SYSTEM DATA created automatically by this idempotent
migration — never by an administrator. Re-running does nothing when the
record already exists.
"""

from alembic import op

revision: str = '043_brain_supplier'
down_revision: str = '042_prom_channel'

UPGRADE_SQL = """
INSERT INTO suppliers (code, name, enabled, created_at, updated_at) VALUES
    ('brain', 'BRAIN', TRUE, NOW(), NOW())
ON CONFLICT (code) DO NOTHING;
"""

DOWNGRADE_SQL = """
DELETE FROM suppliers WHERE code = 'brain';
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)