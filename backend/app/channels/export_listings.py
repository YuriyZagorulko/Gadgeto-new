"""Listing-state persistence helpers for the export engine (Phase 6.3).

All channel_listings / channel_validation_issues writes used by
export_run.py live here.  Duplicates are impossible thanks to the existing
uq_channel_listing unique constraint on (product_id, channel_id).

publication_status = admin intent ('published' once exported successfully);
sync_status        = outcome of the last attempt (syncing/success/error);
last_error_*       = free-form error info safe to show in the admin UI.
"""

from __future__ import annotations

import json

ENUM_PUBLICATION = "channelpublicationstatus"
ENUM_SYNC = "channelsyncstatus"


def upsert_listing_pending(cur, channel_id: int, product_id: int) -> dict:
    """Create-or-fetch the listing row and mark it SYNCING for this attempt."""
    cur.execute(
        "SELECT id, external_id, content_hash, commercial_hash"
        " FROM channel_listings WHERE channel_id=%s AND product_id=%s",
        (channel_id, product_id),
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            f"""INSERT INTO channel_listings
                (product_id, channel_id, publication_status, sync_status,
                 last_attempt_at, created_at, updated_at)
                VALUES (%s, %s, 'DRAFT'::{ENUM_PUBLICATION},
                        'SYNCING'::{ENUM_SYNC}, NOW(), NOW(), NOW())
                ON CONFLICT (channel_id, product_id) DO UPDATE
                   SET last_attempt_at=NOW(),
                       sync_status='SYNCING'::{ENUM_SYNC},
                       updated_at=NOW()
                RETURNING id, external_id, content_hash, commercial_hash""",
            (product_id, channel_id),
        )
    else:
        cur.execute(
            f"""UPDATE channel_listings
                SET last_attempt_at=NOW(),
                    sync_status='SYNCING'::{ENUM_SYNC},
                    updated_at=NOW()
                WHERE id=%s
                RETURNING id, external_id, content_hash, commercial_hash""",
            (row["id"],),
        )
    return cur.fetchone()


def store_validation_issues(cur, listing_id: int, issues: list[dict]) -> None:
    """Replace the stored blocking-issue set for a listing."""
    cur.execute("DELETE FROM channel_validation_issues WHERE listing_id=%s",
                (listing_id,))
    for issue in issues:
        if issue.get("severity") != "error":
            continue
        code = str(issue.get("code") or "UNKNOWN")[:100]
        message = str(issue.get("message") or issue.get("code") or "")[:2000]
        details = json.dumps(issue.get("details") or {}, ensure_ascii=False)
        cur.execute(
            """INSERT INTO channel_validation_issues
               (listing_id, code, message, details_json)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (listing_id, code) DO NOTHING""",
            (listing_id, code, message, details),
        )


def finish_listing_ok(cur, listing: dict, external_id, content_hash: str,
                      commercial_hash: str, remote_status=None) -> None:
    """Success state for one attempt (clears errors + stale issue rows)."""
    cur.execute(
        f"""UPDATE channel_listings
            SET sync_status='SUCCESS'::{ENUM_SYNC},
                publication_status='PUBLISHED'::{ENUM_PUBLICATION},
                external_id=%s, content_hash=%s, commercial_hash=%s,
                remote_status=%s, last_error_type=NULL,
                last_error_message=NULL, last_synced_at=NOW(), updated_at=NOW()
            WHERE id=%s""",
        (external_id, content_hash, commercial_hash, remote_status,
         listing["id"]),
    )
    cur.execute("DELETE FROM channel_validation_issues WHERE listing_id=%s",
                (listing["id"],))


def finish_listing_error(cur, listing_id: int, error_type: str,
                         message: str) -> None:
    message = (message or "")[:2000]
    error_type = (error_type or "invalid_data")[:50]
    cur.execute(
        f"""UPDATE channel_listings
            SET sync_status='ERROR'::{ENUM_SYNC},
                last_error_type=%s, last_error_message=%s, updated_at=NOW()
            WHERE id=%s""",
        (error_type, message, listing_id),
    )
