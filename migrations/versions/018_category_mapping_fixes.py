"""Category mapping fixes from deep audit.

Changes:
1. Fix typo in internal category: "Інструменти для ремонату" → "Інструменти для ремонту" (id=7)
2. Map `Витратні матеріали для палітовки` → `Витратні матеріали` (cat 112)
3. Map `Оперативна пам'ять для серверів` → `Оперативна пам'ять` (cat 28)
4. Map `Оперативна пам`ять для серверів` → `Оперативна пам'ять` (cat 28) [apostrophe variant]
5. Create new internal category `Відеокомутатори` under `Переферія` (cat 40)
6. Map `відеокомутатори` → new `Відеокомутатори` category
7. Map `Відеокомутатори` → new `Відеокомутатори` category
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "018_category_mapping_fixes"
down_revision = "017_import_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    # --- 1. Fix typo in internal category name (id=7) ---
    op.execute(
        """
        UPDATE categories
        SET name = 'Інструменти для ремонту',
            slug = 'інструменти-для-ремонту',
            updated_at = NOW()
        WHERE id = 7 AND name = 'Інструменти для ремонату'
        """
    )

    # --- 2. Create new internal category "Відеокомутатори" under "Переферія" (cat 40) ---
    # Check if it already exists to make migration idempotent
    op.execute(
        """
        INSERT INTO categories (name, slug, parent_id, is_active, sort_order, created_at, updated_at)
        SELECT 'Відеокомутатори', 'відеокомутатори', 40, true, 0, NOW(), NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM categories WHERE slug = 'відеокомутатори' AND parent_id = 40
        )
        """
    )

    # Get the category_id for the newly created or existing "Відеокомутатори"
    new_cat_id = op.execute(
        sa.text("SELECT id FROM categories WHERE name = 'Відеокомутатори' AND parent_id = 40")
    ).scalar()

    # --- 3. Fix mapping 556: Витратні матеріали для палітовки → Витратні матеріали (cat 112) ---
    op.execute(
        """
        UPDATE category_mappings
        SET category_id = 112
        WHERE id = 556
          AND category_id IS NULL
        """
    )

    # --- 4. Fix mapping 463: Оперативна пам'ять для серверів → Оперативна пам'ять (cat 28) ---
    op.execute(
        """
        UPDATE category_mappings
        SET category_id = 28
        WHERE id = 463
          AND category_id IS NULL
        """
    )

    # --- 5. Fix mapping 464: Оперативна пам`ять для серверів → Оперативна пам'ять (cat 28) ---
    op.execute(
        """
        UPDATE category_mappings
        SET category_id = 28
        WHERE id = 464
          AND category_id IS NULL
        """
    )

    # --- 6. Fix mapping 431: відеокомутатори → new Відеокомутатори ---
    op.execute(
        """
        UPDATE category_mappings
        SET category_id = :new_cat_id
        WHERE id = 431
          AND category_id IS NULL
        """.replace(":new_cat_id", str(new_cat_id)) if new_cat_id else ""
    )

    # --- 7. Fix mapping 432: Відеокомутатори → new Відеокомутатори ---
    op.execute(
        """
        UPDATE category_mappings
        SET category_id = :new_cat_id
        WHERE id = 432
          AND category_id IS NULL
        """.replace(":new_cat_id", str(new_cat_id)) if new_cat_id else ""
    )

    # Fallback: if the replace trick didn't work, use raw SQL with the actual ID
    if new_cat_id:
        op.execute(
            f"UPDATE category_mappings SET category_id = {new_cat_id} WHERE id IN (431, 432) AND category_id IS NULL"
        )


def downgrade():
    # --- Revert mapping fixes ---
    op.execute("UPDATE category_mappings SET category_id = NULL WHERE id IN (431, 432, 463, 464, 556)")

    # --- Delete created category ---
    op.execute("DELETE FROM categories WHERE name = 'Відеокомутатори' AND parent_id = 40")

    # --- Revert category rename ---
    op.execute(
        """
        UPDATE categories
        SET name = 'Інструменти для ремонату',
            slug = 'інструменти-для-ремонату',
            updated_at = NOW()
        WHERE id = 7
        """
    )
