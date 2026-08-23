"""012: Seed fixed system suppliers (IT-Link, DC-Link).

Suppliers are SYSTEM DATA created automatically by this idempotent migration —
never by an administrator. Re-running does nothing when records already exist.
"""

from alembic import op

revision: str = '012_system_suppliers'
down_revision: str = '011_password_reset'

UPGRADE_SQL = """
INSERT INTO suppliers (code, name, enabled, created_at, updated_at) VALUES
    ('itlink', 'IT-Link', TRUE, NOW(), NOW()),
    ('dclink', 'DC-Link', TRUE, NOW(), NOW())
ON CONFLICT (code) DO NOTHING;
"""

DOWNGRADE_SQL = """
DELETE FROM suppliers WHERE code IN ('itlink', 'dclink');
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
