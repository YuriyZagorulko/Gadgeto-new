"""008: Add user_id to reviews for storefront submissions.

Additive-only migration. Existing reviews are unaffected.
"""
revision: str = '008_review_user'
down_revision: str = '007_product_editor'

UPGRADE_SQL = """
ALTER TABLE product_reviews
    ADD COLUMN IF NOT EXISTS user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_product_reviews_status ON product_reviews(status);
"""