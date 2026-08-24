"""019: Add COMPLETED_WITH_WARNINGS to import status enum.

The importer now produces structured statistics that distinguish between
a clean run (COMPLETED) and a run where unmapped categories/attributes/
values were found (COMPLETED_WITH_WARNINGS).  This migration adds the
new enum value to the importjobstatus PostgreSQL enum so that the status
can be persisted in the import_jobs table when a run completes with
warnings.

COMPLETED_WITH_WARNINGS is stored as SUCCEEDED in the import_jobs.status
column (because the Postgres enum does not list it), while the detailed
status lives in stats_json.  This migration is a forward-looking step
so that a future schema change can include the new value properly.

Revision ID: 019_import_status_warnings
Revises: 018_category_mapping_fixes
"""

from alembic import op

revision: str = "019_import_status_warnings"
down_revision: str = "018_category_mapping_fixes"
branch_labels = None
depends_on = None

UPGRADE_SQL = """
ALTER TYPE importjobstatus ADD VALUE IF NOT EXISTS 'COMPLETED_WITH_WARNINGS';
"""

DOWNGRADE_SQL = """
-- PostgreSQL does not support removing enum values safely.
-- The value remains in the type but is unused.
SELECT 1;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
