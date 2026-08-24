"""
HTTP client for downloading the IT-Link price list XML.

Uses requests.Session() with the access token to download the price file.
"""

import logging
from pathlib import Path
import shutil

import requests

from app.suppliers.itlink_downloader.config import settings
from app.suppliers.itlink_downloader.exceptions import DownloadError

logger = logging.getLogger(__name__)

# Expected content type for the XML price list
EXPECTED_CONTENT_TYPE = "application/xml"

# Timeouts in seconds
CONNECT_TIMEOUT = 30
READ_TIMEOUT = 120


def download_price_list(access_token: str) -> Path:
    """
    Download the IT-Link price list XML and save it atomically.

    Downloads to a temporary file first, then renames to the final filename
    to prevent corruption from partial downloads.

    Args:
        access_token: A valid OAuth2 access token.

    Returns:
        Path to the saved catalog.xml file.

    Raises:
        DownloadError: If the download fails for any reason.
    """
    logger.info("Downloading XML...")

    # Save directly to catalog/IT-link/itlink.yml
    save_path = settings.target_file_path
    save_path.parent.mkdir(parents=True, exist_ok=True)

    final_path = save_path
    tmp_path = save_path.with_name(save_path.name + ".tmp")

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/xml, application/json, */*",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    })

    try:
        response = session.get(
            settings.price_url,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            stream=True,
        )

        # Validate HTTP status
        if response.status_code == 401:
            raise DownloadError(
                "HTTP 401 Unauthorized. The access token may be expired or invalid.",
                status_code=401,
            )
        elif response.status_code == 403:
            raise DownloadError(
                "HTTP 403 Forbidden. The access token lacks sufficient permissions.",
                status_code=403,
            )
        elif response.status_code != 200:
            raise DownloadError(
                f"HTTP {response.status_code} received while downloading price list. "
                f"Expected 200.",
                status_code=response.status_code,
            )

        # Validate content type
        content_type = response.headers.get("Content-Type", "")
        if EXPECTED_CONTENT_TYPE not in content_type:
            raise DownloadError(
                f"Unexpected Content-Type: '{content_type}'. "
                f"Expected content type containing '{EXPECTED_CONTENT_TYPE}'. "
                f"The response may not be a valid XML price list.",
            )

        # Write to temporary file
        with open(tmp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # Verify the file is not empty
        if tmp_path.stat().st_size == 0:
            tmp_path.unlink(missing_ok=True)
            raise DownloadError("Downloaded file is empty (0 bytes).")

        # Verify it's valid XML by reading the first few bytes
        try:
            with open(tmp_path, "rb") as f:
                header = f.read(100)
                if not header.strip().startswith(b"<") and not header.strip().startswith(b"<?xml"):
                    tmp_path.unlink(missing_ok=True)
                    raise DownloadError(
                        "Downloaded file does not appear to be valid XML. "
                        f"File starts with: {header[:50]!r}"
                    )
        except OSError as exc:
            tmp_path.unlink(missing_ok=True)
            raise DownloadError(f"Failed to verify downloaded file: {exc}") from exc

        # Atomic rename: replace the old file with the new one
        shutil.move(str(tmp_path), str(final_path))

    except requests.exceptions.Timeout as exc:
        raise DownloadError(
            f"Request timed out while downloading price list: {exc}"
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise DownloadError(
            f"Connection error while downloading price list: {exc}"
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise DownloadError(
            f"Request failed while downloading price list: {exc}"
        ) from exc
    finally:
        session.close()
        # Clean up temp file if it still exists
        tmp_path.unlink(missing_ok=True)

    logger.info("Download completed.")
    logger.info("Saved: %s", final_path)
    return final_path