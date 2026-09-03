"""
Email service using Brevo (Sendinblue) API for transactional emails.
"""
import html
import json
import logging
import re
from typing import List, Optional

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


# ── Catalog sync failure notifications (admin alerts) ────────────────────────

CATALOG_SYNC_FAILURE_HTML = """\
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ margin: 0; padding: 0; background-color: #f4f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .header {{ background-color: #dc2626; padding: 32px 24px; text-align: center; }}
        .header h1 {{ color: #ffffff; margin: 0; font-size: 22px; font-weight: 700; }}
        .body {{ padding: 32px 24px; color: #1f2937; }}
        .body p {{ font-size: 15px; line-height: 1.6; margin: 0 0 16px; }}
        .meta {{ background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px 16px; font-size: 14px; margin: 0 0 20px; }}
        .meta div {{ margin: 3px 0; }}
        .meta span.label {{ color: #6b7280; }}
        .failures {{ border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; margin: 0 0 20px; }}
        .failures div.row {{ padding: 12px 16px; border-bottom: 1px solid #e5e7eb; font-size: 14px; }}
        .failures div.row:last-child {{ border-bottom: none; }}
        .failures .name {{ font-weight: 600; }}
        .failures .error {{ color: #b91c1c; word-break: break-word; margin-top: 4px; }}
        .footer {{ padding: 24px; text-align: center; font-size: 13px; color: #9ca3af; border-top: 1px solid #e5e7eb; }}
    </style>
</head>
<body>
    <table width="100%" cellpadding="0" cellspacing="0" style="padding: 24px 16px; background-color: #f4f4f6;">
        <tr><td align="center">
            <div class="container">
                <div class="header">
                    <h1>Синхронізація каталогу — {status_label}</h1>
                </div>
                <div class="body">
                    <p>Автоматична синхронізація каталогу завершилась із помилками. Перелік проблем — нижче.</p>
                    <div class="meta">
                        <div><span class="label">Запуск:</span> #{run_id}</div>
                        <div><span class="label">Запуск ініційовано:</span> {trigger_label}</div>
                        <div><span class="label">Початок:</span> {started}</div>
                        <div><span class="label">Завершення:</span> {finished}</div>
                        <div><span class="label">Статус:</span> {status_label}</div>
                    </div>
                    <div class="failures">
                        {failures_html}
                    </div>
                    <p>Деталі та журнал запуску доступні в адмін-панелі: <strong>Автоматизація</strong>.</p>
                </div>
                <div class="footer">
                    <p>© Gadgeto. Це автоматичне повідомлення. Будь ласка, не відповідайте на нього.</p>
                </div>
            </div>
        </td></tr>
    </table>
</body>
</html>
"""
CATALOG_SYNC_FAILURE_TEXT = """\
Синхронізація каталогу — {status_label}

Автоматична синхронізація каталогу завершилась із помилками.

Запуск: #{run_id}
Запуск ініційовано: {trigger_label}
Початок: {started}
Завершення: {finished}
Статус: {status_label}

Проблеми:
{failures_text}

Деталі та журнал запуску — в адмін-панелі, розділ «Автоматизація».

© Gadgeto. Це автоматичне повідомлення.
"""

_FAILURE_SOURCE_LABELS = {
    "supplier": "Постачальник",
    "channel": "Платформа експорту",
}

_STATUS_LABELS = {
    "FAILED": "помилка",
    "PARTIAL": "частковий успіх (є помилки)",
}

_TRIGGER_LABELS = {
    "scheduler": "автоматично (за розкладом)",
    "manual": "вручну з адмін-панелі",
}


def _parse_admin_recipients() -> List[str]:
    """Parse ADMIN_NOTIFICATION_EMAILS (JSON array or comma-separated list).

    Kept tolerant on purpose: a malformed value must never crash backend
    startup, it just results in fewer/no recipients.
    """
    raw = (settings.ADMIN_NOTIFICATION_EMAILS or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except (json.JSONDecodeError, TypeError):
            logger.warning("ADMIN_NOTIFICATION_EMAILS: invalid JSON — falling "
                           "back to comma-separated parsing")
    parts = [part.strip(" \t[]") for part in re.split(r"[;,]", raw)]
    return [part for part in parts if part]


def _format_failure_dt(value) -> str:
    """Human-readable started/finished timestamp (datetime, str or None)."""
    if value is None:
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y %H:%M:%S")
    return str(value)


def _failures_html(failures: List[dict]) -> str:
    rows = []
    for f in failures:
        source = _FAILURE_SOURCE_LABELS.get(f.get("source"), f.get("source") or "Джерело")
        name = html.escape(str(f.get("name") or "невідомо"))
        err = html.escape(str(f.get("error") or "причина не вказана"))
        rows.append(
            f'<div class="row"><span class="name">{html.escape(source)}: {name}</span>'
            f'<div class="error">{err}</div></div>'
        )
    return "".join(rows) or '<div class="row">Деталі відсутні.</div>'


def _failures_text(failures: List[dict]) -> str:
    lines = []
    for f in failures:
        source = _FAILURE_SOURCE_LABELS.get(f.get("source"), f.get("source") or "Джерело")
        err = str(f.get("error") or "причина не вказана")
        lines.append(f"- {source}: {f.get('name') or 'невідомо'} — {err}")
    return "\n".join(lines) or "Деталі відсутні."


def send_catalog_sync_failure_email(
    run_id: int,
    status: str,
    trigger: str,
    failures: List[dict],
    started_at=None,
    finished_at=None,
) -> bool:
    """Notify admins that a catalog sync run finished with errors.

    Synchronous on purpose: the caller is the Celery worker (blocking
    context), NOT the FastAPI event loop. One Brevo API call delivers the
    message to every configured recipient.

    Args:
        run_id: catalog sync run id.
        status: final run status ("FAILED" or "PARTIAL").
        trigger: run trigger ("scheduler" or "manual").
        failures: list of dicts with keys `source` ("supplier"|"channel"),
            `name`, and optional `status`/`error`.
        started_at / finished_at: run timestamps (datetime or str).

    Returns:
        True if the email was sent (or logged in dev fallback), else False.

    Raises:
        RuntimeError: If BREVO_API_KEY is not configured in production
            (callers must treat email problems as non-fatal).
    """
    recipients = _parse_admin_recipients()
    if not recipients:
        logger.info(
            "ADMIN_NOTIFICATION_EMAILS is not configured — "
            "catalog sync failure notification skipped (run #%s)", run_id,
        )
        return False

    status_label = _STATUS_LABELS.get(status, status)
    trigger_label = _TRIGGER_LABELS.get(trigger, trigger)
    subject = f"Gadgeto: синхронізація каталогу — {status_label} (запуск #{run_id})"

    html_body = CATALOG_SYNC_FAILURE_HTML.format(
        run_id=run_id, status_label=status_label, trigger_label=trigger_label,
        started=_format_failure_dt(started_at),
        finished=_format_failure_dt(finished_at),
        failures_html=_failures_html(failures),
    )
    text_body = CATALOG_SYNC_FAILURE_TEXT.format(
        run_id=run_id, status_label=status_label, trigger_label=trigger_label,
        started=_format_failure_dt(started_at),
        finished=_format_failure_dt(finished_at),
        failures_text=_failures_text(failures),
    )

    payload = {
        "sender": {
            "email": settings.BREVO_SENDER_EMAIL or "noreply@gadgeto.com.ua",
            "name": settings.BREVO_SENDER_NAME or "Gadgeto",
        },
        "to": [{"email": email} for email in recipients],
        "subject": subject,
        "htmlContent": html_body,
        "textContent": text_body,
    }

    headers = _get_headers()

    # In development without API key, log the email instead of sending
    if not headers or not headers.get("api-key"):
        logger.info(
            "[DEV EMAIL] To: %s | Subject: %s | run #%s (%s)",
            ", ".join(recipients), subject, run_id, status,
        )
        print(
            f"\n{'='*60}\n"
            f"  DEV EMAIL to: {', '.join(recipients)}\n"
            f"  Subject: {subject}\n"
            f"  Failures: {_failures_text(failures)}\n"
            f"{'='*60}\n"
        )
        return True

    try:
        with httpx.Client(timeout=httpx.Timeout(15.0, connect=10.0)) as client:
            response = client.post(
                f"{BREVO_API_URL}/smtp/email",
                json=payload,
                headers=headers,
            )
            if response.is_success:
                logger.info(
                    "Catalog sync failure email sent to %s via Brevo "
                    "(run #%s, message_id=%s)",
                    ", ".join(recipients), run_id,
                    response.json().get("messageId", "unknown"),
                )
                return True
            logger.error(
                "Brevo catalog-sync failure send failed (run #%s): HTTP %d, body=%s",
                run_id, response.status_code, response.text,
            )
            return False
    except httpx.TimeoutException:
        logger.error("Timeout sending catalog sync failure email (run #%s)", run_id)
        return False
    except Exception as exc:
        logger.error("Error sending catalog sync failure email (run #%s): %s", run_id, exc)
        return False
