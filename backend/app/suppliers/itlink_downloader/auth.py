"""
Authentication module for IT-Link.

Uses Playwright to perform OAuth2 Authorization Code + PKCE flow
and intercept the access token from the /connect/token response.
"""

import logging
from typing import Optional

from playwright.sync_api import sync_playwright

from app.suppliers.itlink_downloader.config import settings
from app.suppliers.itlink_downloader.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

# URL patterns
_TOKEN_URL = "https://auth.it-link.com.ua/connect/token"
_LOGIN_URL = "https://auth.it-link.com.ua/Account/Login"


def get_access_token() -> str:
    """
    Authenticate with IT-Link and return an access token.

    Launches a headless Playwright browser, navigates to it-link.ua,
    clicks the login button, handles the OAuth login redirect,
    and intercepts the access token from the /connect/token response.

    Returns:
        The access token string.

    Raises:
        AuthenticationError: If authentication fails for any reason.
    """
    logger.info("Starting authentication...")

    token: Optional[str] = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=settings.headless,
                args=['--no-sandbox', '--disable-gpu'],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                no_viewport=True,
            )
            page = context.new_page()

            # Intercept the /connect/token response
            def _on_response(response):
                nonlocal token
                if _TOKEN_URL in response.url and response.status == 200:
                    try:
                        data = response.json()
                        access_token = data.get("access_token")
                        if access_token:
                            token = access_token
                            logger.info(
                                "Access token intercepted from /connect/token response."
                            )
                        else:
                            raise AuthenticationError(
                                "Token response did not contain 'access_token'."
                            )
                    except ValueError as exc:
                        raise AuthenticationError(
                            f"Failed to parse token response JSON: {exc}"
                        ) from exc

            page.on("response", _on_response)

            # Navigate to the main site to trigger the OAuth flow
            logger.info("Navigating to it-link.ua...")
            page.goto(settings.base_url, wait_until="networkidle")

            # Click the login button to trigger OAuth redirect
            logger.info("Clicking login button...")
            page.locator('button[aria-label="login"]').dispatch_event("click")
            try:
                page.wait_for_url(f"{_LOGIN_URL}**", timeout=15_000)
            except Exception:
                page.goto(_LOGIN_URL, wait_until="networkidle")
            logger.info("Redirected to login page. Filling credentials...")

            # Fill username
            page.locator("#Username").wait_for(timeout=10_000)
            page.locator("#Username").fill(settings.username)

            # Fill password
            page.locator("#Password").wait_for(timeout=10_000)
            page.locator("#Password").fill(settings.password)

            # Click the login button
            page.locator('button[value="login"]').click()

            logger.info("Waiting for authentication to complete...")
            # Wait for the token to be intercepted (up to 30 seconds)
            for _ in range(60):
                if token is not None:
                    break
                page.wait_for_timeout(500)

            if token is None:
                # Check for login error message
                error_elem = page.locator('.validation-summary-errors li').first
                if error_elem.count():
                    error_text = error_elem.text_content()
                    raise AuthenticationError(
                        f"Login failed: {error_text}. "
                        f"Check your ITLINK_USERNAME/ITLINK_PASSWORD in .env"
                    )
                raise AuthenticationError(
                    "Access token was not obtained within the timeout period. "
                    "The /connect/token response was not intercepted. "
                    f"Current URL: {page.url}"
                )

            logger.info("Authentication successful.")
            browser.close()

    except AuthenticationError:
        raise
    except Exception as exc:
        raise AuthenticationError(
            f"Authentication failed: {exc}"
        ) from exc

    if not token:
        raise AuthenticationError(
            "Access token was not obtained. "
            "The /connect/token response was not intercepted."
        )

    logger.info("Access token received.")
    return token