"""015: Import progress tracking columns.

Adds columns needed for real-time import job monitoring:
- progress_json: current progress state (stage, counts, percentage)
- current_stage: human-readable current stage name
"""

from alembic import op

revision: str = '015_import_progress'
down_revision: str = '014_global_mappings'

UPGRADE_SQL = """
ALTER TABLE import_jobs
    ADD COLUMN IF NOT EXISTS progress_json TEXT,
    ADD COLUMN IF NOT EXISTS current_stage VARCHAR(255);
"""

DOWNGRADE_SQL = """
ALTER TABLE import_jobs
    DROP COLUMN IF EXISTS current_stage,
    DROP COLUMN IF EXISTS progress_json;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
