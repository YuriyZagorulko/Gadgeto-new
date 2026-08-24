"""021: Remove legacy product_attributes for catch-all attributes #167, #193, #206.

After migration 020 split the catch-all attributes into specific new attributes,
the old product_attributes rows containing merged/ambiguous values must be
removed.  The next full supplier import will populate the correct attributes
with clean data from supplier feeds.

Changes:
- DELETE product_attributes WHERE attribute_id IN (167, 193, 206)

Preserves:
- The attributes themselves (#167, #193, #206 remain as catalog entries)
- attribute_values
- supplier_attributes, supplier_attribute_values
- attribute_mappings, attribute_value_mappings
- All other product_attributes (including #183, #282, #315, new attrs 331-355)
- products, categories, brands, suppliers, users, orders

Revision ID: 021_clean_historical_catchall_attrs
Revises: 020_attribute_taxonomy_cleanup
"""

from alembic import op
import sqlalchemy as sa

revision: str = "021_clean_historical_catchall_attrs"
down_revision: str = "020_attribute_taxonomy_cleanup"
branch_labels = None
depends_on = None

TARGET_ATTRS = (167, 193, 206)


def upgrade():
    conn = op.get_bind()

    # Double-check counts for audit trail
    total = 0
    for attr_id in TARGET_ATTRS:
        row = conn.execute(
            sa.text(
                "SELECT COUNT(*) AS cnt, "
                "COUNT(DISTINCT product_id) AS products, "
                "COUNT(DISTINCT value_text) AS values "
                "FROM product_attributes WHERE attribute_id = :aid"
            ),
            {"aid": attr_id},
        ).fetchone()
        cnt = row[0]
        prod = row[1]
        vals = row[2]
        total += cnt
        print(f"  #{attr_id}: {cnt} rows ({prod} products, {vals} distinct values)")

    print(f"  TOTAL: {total} rows to delete")

    # Execute the deletion
    result = conn.execute(
        sa.text(
            "DELETE FROM product_attributes WHERE attribute_id IN (:a1, :a2, :a3)"
        ),
        {"a1": 167, "a2": 193, "a3": 206},
    )

    print(f"  DELETED: {result.rowcount} rows")


def downgrade():
    """Downgrade is NOT SUPPORTED because the deleted historical data
    cannot be safely reconstructed.  The original product_attributes rows
    contained ambiguous merged values (e.g., compound | values, mixed
    HDD/RAM/SSD entries under #193) that cannot be recreated without
    re-importing from the original supplier feeds.

    Perform a full supplier re-import to restore product attributes.
    """
    print("WARNING: Downgrade cannot restore deleted product_attributes rows.")
    print("Run a full supplier import to repopulate attributes.")
