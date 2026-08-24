"""
Image download helper for supplier imports.

When the supplier's image_storage_mode is set to 'local', imported product
images are downloaded and stored in the local media storage instead of
keeping external URLs.

Deduplication is done via SHA-256 hash: if the same image already exists
in media_files, the existing record is reused.
"""
import hashlib
import logging
import os
import uuid
from typing import Optional, Tuple

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
EXT_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
DOWNLOAD_TIMEOUT = (10, 30)  # connect, read
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


def download_supplier_image(image_url: str, cur) -> Optional[dict]:
    """
    Download a supplier image and create/reuse a media_files record.

    Args:
        image_url: The supplier's image URL.
        cur: Database cursor (autocommit mode).

    Returns:
        dict with 'url' (local media URL) and 'media_id' (media_files.id),
        or None if the download failed.
    """
    try:
        response = requests.get(image_url, timeout=DOWNLOAD_TIMEOUT, stream=True)
        if response.status_code != 200:
            logger.warning("Image download failed (HTTP %s): %s", response.status_code, image_url)
            return None

        content_type = response.headers.get("Content-Type", "")
        if content_type not in ALLOWED_MIME and not any(
            content_type.startswith(m.split("/")[0]) for m in ALLOWED_MIME
        ):
            # Try to detect from extension
            ext = os.path.splitext(image_url.split("?")[0])[1].lower()
            if ext in (".jpg", ".jpeg"):
                content_type = "image/jpeg"
            elif ext == ".png":
                content_type = "image/png"
            elif ext == ".webp":
                content_type = "image/webp"
            elif ext == ".gif":
                content_type = "image/gif"
            else:
                logger.warning("Unsupported image type '%s' for: %s", content_type, image_url)
                return None

        body = b""
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                body += chunk
                if len(body) > MAX_SIZE:
                    logger.warning("Image too large (>10MB): %s", image_url)
                    return None

        if not body:
            logger.warning("Empty image body: %s", image_url)
            return None

        # SHA-256 deduplication
        sha256 = hashlib.sha256(body).hexdigest()
        cur.execute("SELECT id, url, storage_path FROM media_files WHERE sha256 = %s", (sha256,))
        existing = cur.fetchone()
        if existing:
            # Reuse existing media record
            logger.info("Reusing existing media (sha256=%s) for: %s", sha256[:12], image_url)
            return {"url": existing["url"], "media_id": existing["id"]}

        mime = content_type
        ext = EXT_BY_MIME.get(mime, ".jpg")
        filename = uuid.uuid4().hex + ext
        rel_path = f"products/{filename}"
        abs_path = os.path.join(settings.MEDIA_DIR, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        with open(abs_path, "wb") as f:
            f.write(body)

        base_url = (settings.MEDIA_BASE_URL or "/media").rstrip("/")
        local_url = f"{base_url}/{rel_path}"

        # Detect dimensions
        width = height = None
        try:
            from PIL import Image
            import io
            with Image.open(io.BytesIO(body)) as im:
                width, height = im.size
        except Exception:
            pass

        cur.execute(
            """INSERT INTO media_files (filename, storage_path, url, mime_type,
                                        size_bytes, width, height, sha256)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (filename, rel_path, local_url, mime, len(body), width, height, sha256),
        )
        media_id = cur.fetchone()["id"]
        logger.info("Downloaded and stored image: %s -> %s", image_url, local_url)
        return {"url": local_url, "media_id": media_id}

    except requests.exceptions.Timeout:
        logger.warning("Image download timeout: %s", image_url)
    except requests.exceptions.ConnectionError:
        logger.warning("Image connection error: %s", image_url)
    except requests.exceptions.RequestException as e:
        logger.warning("Image download error %s: %s", image_url, e)
    except OSError as e:
        logger.warning("Image file error %s: %s", image_url, e)
    except Exception as e:
        logger.warning("Unexpected image error %s: %s", image_url, e)

    return None