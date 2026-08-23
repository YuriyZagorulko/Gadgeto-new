"""
Email service using Brevo (Sendinblue) API for transactional emails.
"""
import logging
import re
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3"

# ── Email templates ──────────────────────────────────────────────────────────

VERIFICATION_EMAIL_HTML = """\
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ margin: 0; padding: 0; background-color: #f4f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .header {{ background-color: #2563eb; padding: 32px 24px; text-align: center; }}
        .header h1 {{ color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; }}
        .body {{ padding: 32px 24px; color: #1f2937; }}
        .body p {{ font-size: 16px; line-height: 1.6; margin: 0 0 20px; }}
        .button {{ display: inline-block; background-color: #2563eb; color: #ffffff !important; text-decoration: none; padding: 14px 36px; border-radius: 8px; font-size: 16px; font-weight: 600; margin: 16px 0; }}
        .button:hover {{ background-color: #1d4ed8; }}
        .fallback {{ font-size: 14px; color: #6b7280; word-break: break-all; margin-top: 20px; }}
        .footer {{ padding: 24px; text-align: center; font-size: 13px; color: #9ca3af; border-top: 1px solid #e5e7eb; }}
        .footer p {{ margin: 4px 0; }}
        .expiry {{ font-size: 13px; color: #9ca3af; margin-top: 16px; }}
    </style>
</head>
<body>
    <table width="100%" cellpadding="0" cellspacing="0" style="padding: 24px 16px; background-color: #f4f4f6;">
        <tr><td align="center">
            <div class="container">
                <div class="header">
                    <h1>Gadgeto</h1>
                </div>
                <div class="body">
                    <p><strong>Вітаємо в Gadgeto!</strong></p>
                    <p>Дякуємо за реєстрацію. Щоб підтвердити вашу електронну адресу та активувати обліковий запис, натисніть кнопку нижче.</p>
                    <p style="text-align: center;">
                        <a href="{verification_url}" class="button">Підтвердити email</a>
                    </p>
                    <p class="expiry">Посилання дійсне протягом 24 годин.</p>
                    <p class="fallback">Якщо кнопка не працює, скопіюйте та вставте посилання у браузер:<br><a href="{verification_url}" style="color: #2563eb;">{verification_url}</a></p>
                </div>
                <div class="footer">
                    <p>© Gadgeto. Усі права захищені.</p>
                    <p>Це автоматичне повідомлення. Будь ласка, не відповідайте на нього.</p>
                </div>
            </div>
        </td></tr>
    </table>
</body>
</html>
"""

VERIFICATION_EMAIL_TEXT = """\
Вітаємо в Gadgeto!

Дякуємо за реєстрацію. Щоб підтвердити вашу електронну адресу та активувати обліковий запис, перейдіть за посиланням:

{verification_url}

Посилання дійсне протягом 24 годин.

© Gadgeto. Усі права захищені.
"""


# ── Email sending ────────────────────────────────────────────────────────────


def _get_headers() -> dict:
    """Get Brevo API headers."""
    api_key = settings.BREVO_API_KEY
    if not api_key:
        if settings.ENVIRONMENT == "development":
            logger.warning(
                "BREVO_API_KEY is not configured. "
                "Emails will be logged instead of sent."
            )
            return {}  # Will trigger fallback logging
        raise RuntimeError(
            "BREVO_API_KEY is not configured. "
            "Set the BREVO_API_KEY environment variable to enable email sending."
        )
    return {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def send_verification_email(
    to_email: str,
    to_name: str,
    verification_url: str,
) -> bool:
    """
    Send email verification link via Brevo.

    Args:
        to_email: Recipient email address.
        to_name: Recipient display name.
        verification_url: Full verification URL (with token).

    Returns:
        True on success, False on failure.

    Raises:
        RuntimeError: If BREVO_API_KEY is not configured.
    """
    sender_email = settings.BREVO_SENDER_EMAIL or "noreply@gadgeto.com.ua"
    sender_name = settings.BREVO_SENDER_NAME or "Gadgeto"

    html_body = VERIFICATION_EMAIL_HTML.format(verification_url=verification_url)
    text_body = VERIFICATION_EMAIL_TEXT.format(verification_url=verification_url)

    payload = {
        "sender": {"email": sender_email, "name": sender_name},
        "to": [{"email": to_email, "name": to_name}],
        "subject": "Підтвердження електронної пошти — Gadgeto",
        "htmlContent": html_body,
        "textContent": text_body,
    }

    headers = _get_headers()

    # In development without API key, log the email instead of sending
    if not headers or not headers.get("api-key"):
        logger.info(
            "[DEV EMAIL] To: %s <%s> | Subject: %s | URL: %s",
            to_name,
            to_email,
            "Підтвердження електронної пошти — Gadgeto",
            verification_url,
        )
        print(
            f"\n{'='*60}\n"
            f"  DEV EMAIL to: {to_name} <{to_email}>\n"
            f"  Subject: Підтвердження електронної пошти — Gadgeto\n"
            f"  Verification URL: {verification_url}\n"
            f"{'='*60}\n"
        )
        return True

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{BREVO_API_URL}/smtp/email",
                json=payload,
                headers=headers,
            )
            if response.is_success:
                logger.info(
                    "Verification email sent to %s via Brevo (message_id=%s)",
                    to_email,
                    response.json().get("messageId", "unknown"),
                )
                return True
            else:
                logger.error(
                    "Brevo send failed for %s: HTTP %d, body=%s",
                    to_email,
                    response.status_code,
                    response.text,
                )
                return False
    except httpx.TimeoutException:
        logger.error("Timeout sending verification email to %s via Brevo", to_email)
        return False
    except Exception as exc:
        logger.error("Error sending verification email to %s: %s", to_email, exc)
        return False


# ── Password Reset email ──────────────────────────────────────────────────────

PASSWORD_RESET_HTML = """\
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ margin: 0; padding: 0; background-color: #f4f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .header {{ background-color: #2563eb; padding: 32px 24px; text-align: center; }}
        .header h1 {{ color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; }}
        .body {{ padding: 32px 24px; color: #1f2937; }}
        .body p {{ font-size: 16px; line-height: 1.6; margin: 0 0 20px; }}
        .button {{ display: inline-block; background-color: #2563eb; color: #ffffff !important; text-decoration: none; padding: 14px 36px; border-radius: 8px; font-size: 16px; font-weight: 600; margin: 16px 0; }}
        .button:hover {{ background-color: #1d4ed8; }}
        .fallback {{ font-size: 14px; color: #6b7280; word-break: break-all; margin-top: 20px; }}
        .footer {{ padding: 24px; text-align: center; font-size: 13px; color: #9ca3af; border-top: 1px solid #e5e7eb; }}
        .footer p {{ margin: 4px 0; }}
        .expiry {{ font-size: 13px; color: #9ca3af; margin-top: 16px; }}
    </style>
</head>
<body>
    <table width="100%" cellpadding="0" cellspacing="0" style="padding: 24px 16px; background-color: #f4f4f6;">
        <tr><td align="center">
            <div class="container">
                <div class="header">
                    <h1>Gadgeto</h1>
                </div>
                <div class="body">
                    <p><strong>Відновлення пароля</strong></p>
                    <p>Ви отримали цей лист, тому що запросили відновлення пароля для вашого облікового запису Gadgeto.</p>
                    <p style="text-align: center;">
                        <a href="{reset_url}" class="button">Відновити пароль</a>
                    </p>
                    <p class="expiry">Посилання дійсне протягом 1 години.</p>
                    <p class="fallback">Якщо кнопка не працює, скопіюйте та вставте посилання у браузер:<br><a href="{reset_url}" style="color: #2563eb;">{reset_url}</a></p>
                    <p style="font-size: 14px; color: #6b7280; margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb;">
                        Якщо ви не запитували відновлення пароля, просто проігноруйте цей лист. Ваш акаунт у безпеці.
                    </p>
                </div>
                <div class="footer">
                    <p>© Gadgeto. Усі права захищені.</p>
                    <p>Це автоматичне повідомлення. Будь ласка, не відповідайте на нього.</p>
                </div>
            </div>
        </td></tr>
    </table>
</body>
</html>
"""

PASSWORD_RESET_TEXT = """\
Відновлення пароля — Gadgeto

Ви отримали цей лист, тому що запросили відновлення пароля для вашого облікового запису Gadgeto.

Щоб відновити пароль, перейдіть за посиланням:

{reset_url}

Посилання дійсне протягом 1 години.

Якщо ви не запитували відновлення пароля, просто проігноруйте цей лист. Ваш акаунт у безпеці.

© Gadgeto. Усі права захищені.
"""


async def send_password_reset_email(
    to_email: str,
    to_name: str,
    reset_url: str,
) -> bool:
    """
    Send a password reset email via Brevo.

    Args:
        to_email: Recipient email address.
        to_name: Recipient display name.
        reset_url: Full password reset URL (with token).

    Returns:
        True on success, False on failure.

    Raises:
        RuntimeError: If BREVO_API_KEY is not configured.
    """
    sender_email = settings.BREVO_SENDER_EMAIL or "noreply@gadgeto.com.ua"
    sender_name = settings.BREVO_SENDER_NAME or "Gadgeto"

    html_body = PASSWORD_RESET_HTML.format(reset_url=reset_url)
    text_body = PASSWORD_RESET_TEXT.format(reset_url=reset_url)

    payload = {
        "sender": {"email": sender_email, "name": sender_name},
        "to": [{"email": to_email, "name": to_name}],
        "subject": "Відновлення пароля — Gadgeto",
        "htmlContent": html_body,
        "textContent": text_body,
    }

    headers = _get_headers()

    # In development without API key, log the email instead of sending
    if not headers or not headers.get("api-key"):
        logger.info(
            "[DEV EMAIL] To: %s <%s> | Subject: %s | URL: %s",
            to_name,
            to_email,
            "Відновлення пароля — Gadgeto",
            reset_url,
        )
        print(
            f"\n{'='*60}\n"
            f"  DEV EMAIL to: {to_name} <{to_email}>\n"
            f"  Subject: Відновлення пароля — Gadgeto\n"
            f"  Reset URL: {reset_url}\n"
            f"{'='*60}\n"
        )
        return True

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{BREVO_API_URL}/smtp/email",
                json=payload,
                headers=headers,
            )
            if response.is_success:
                logger.info(
                    "Password reset email sent to %s via Brevo (message_id=%s)",
                    to_email,
                    response.json().get("messageId", "unknown"),
                )
                return True
            else:
                logger.error(
                    "Brevo password-reset send failed for %s: HTTP %d, body=%s",
                    to_email,
                    response.status_code,
                    response.text,
                )
                return False
    except httpx.TimeoutException:
        logger.error("Timeout sending password reset email to %s via Brevo", to_email)
        return False
    except Exception as exc:
        logger.error("Error sending password reset email to %s: %s", to_email, exc)
        return False
