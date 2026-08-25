"""009: Media library - central media_files entity with metadata and usage tracking.

Additive-only:
- new `media_files` table (one row per physical uploaded file);
- nullable `media_id` FK on product_images linking rows to media;
- backfills media_files from existing locally-stored product_images
  (/media/... URLs); external URLs are NOT imported.
"""
from alembic import op
import sqlalchemy as sa

revision: str = '009_media_library'
down_revision: str = '008_review_user'

UPGRADE_SQL = """
CREATE TABLE IF NOT EXISTS media_files (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    storage_path VARCHAR(500) NOT NULL UNIQUE,
    url VARCHAR(1000) NOT NULL,
    mime_type VARCHAR(100) NOT NULL DEFAULT 'application/octet-stream',
    size_bytes BIGINT NOT NULL DEFAULT 0,
    width INTEGER NULL,
    height INTEGER NULL,
    sha256 VARCHAR(64) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_media_files_url ON media_files(url);

ALTER TABLE product_images
    ADD COLUMN IF NOT EXISTS media_id INTEGER NULL REFERENCES media_files(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_product_images_media ON product_images(media_id);

-- Backfill: import existing local uploads into media_files
INSERT INTO media_files (filename, storage_path, url, mime_type, size_bytes)
SELECT
    split_part(replace(pi.url, '/media/', ''), '/', -1),
    replace(pi.url, '/media/', ''),
    pi.url,
    CASE
        WHEN pi.url ILIKE '%.webp' THEN 'image/webp'
        WHEN pi.url ILIKE '%.png'  THEN 'image/png'
        WHEN pi.url ILIKE '%.gif'  THEN 'image/gif'
        ELSE 'image/jpeg'
    END,
    0
FROM product_images pi
WHERE pi.url LIKE '/media/%'
ON CONFLICT (storage_path) DO NOTHING;

UPDATE product_images pi
SET media_id = m.id
FROM media_files m
WHERE pi.url LIKE '/media/%' AND m.url = pi.url AND pi.media_id IS NULL;
"""


def upgrade() -> None:
    """Execute the idempotent SQL (additive, IF NOT EXISTS / ON CONFLICT DO NOTHING)."""
    op.execute(sa.text(UPGRADE_SQL))


def downgrade() -> None:
    """Historically this was a manual additive migration with no defined
    rollback.  The table, column, indexes and data backfill added here are
    now depended upon by later migrations and application code.  Rollback is
    intentionally not implemented."""
    pass