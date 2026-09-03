"""Unit tests for catalog sync failure email notifications."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx

from app.core.config import settings
from app.services.email import (
    _failures_html,
    _failures_text,
    _parse_admin_recipients,
    send_catalog_sync_failure_email,
)
from app.tasks import state
from app.tasks.catalog_sync import after_channel_exports, after_supplier_imports


# ── ADMIN_NOTIFICATION_EMAILS parsing ────────────────────────────────────────


class TestAdminRecipientsParsing:
    def test_json_array(self, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAILS",
                            '["a@example.com", "b@example.com"]')
        assert _parse_admin_recipients() == ["a@example.com", "b@example.com"]

    def test_comma_separated(self, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAILS",
                            "a@example.com,b@example.com")
        assert _parse_admin_recipients() == ["a@example.com", "b@example.com"]

    def test_semicolon_separated(self, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAILS",
                            "a@example.com;b@example.com")
        assert _parse_admin_recipients() == ["a@example.com", "b@example.com"]

    def test_invalid_json_falls_back_to_split(self, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAILS",
                            "[a@example.com,b@example.com]")
        assert _parse_admin_recipients() == ["a@example.com", "b@example.com"]

    def test_empty_disables(self, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAILS", "")
        assert _parse_admin_recipients() == []

    def test_whitespace_entries_filtered(self, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAILS",
                            " a@example.com , , b@example.com ")
        assert _parse_admin_recipients() == ["a@example.com", "b@example.com"]


# ── Failure email sender ─────────────────────────────────────────────────────


FAILURES = [
    {"source": "supplier", "name": "itlink", "status": "FAILED",
     "error": "feed download failed"},
    {"source": "channel", "name": "rozetka", "status": "FAILED",
     "error": "API 500"},
]


def _mock_http(is_success: bool = True, status_code: int = 201):
    response = MagicMock()
    response.is_success = is_success
    response.status_code = status_code
    response.json.return_value = {"messageId": "msg-1"}
    response.text = "body"
    client = MagicMock()
    client.post.return_value = response
    context = MagicMock()
    context.__enter__.return_value = client
    context.__exit__.return_value = False
    return client, context


class TestSendCatalogSyncFailureEmail:
    def test_no_recipients_skips_http(self, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAILS", "")
        with patch("app.services.email.httpx.Client") as mock_client:
            result = send_catalog_sync_failure_email(
                run_id=1, status="FAILED", trigger="scheduler", failures=FAILURES,
            )
        assert result is False
        mock_client.assert_not_called()

    def test_dev_fallback_without_api_key(self, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAILS",
                            '["a@example.com"]')
        monkeypatch.setattr(settings, "BREVO_API_KEY", "")
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        with patch("app.services.email.httpx.Client") as mock_client:
            result = send_catalog_sync_failure_email(
                run_id=2, status="PARTIAL", trigger="manual", failures=FAILURES,
            )
        assert result is True
        mock_client.assert_not_called()

    def test_successful_send_builds_correct_payload(self, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAILS",
                            '["a@example.com", "b@example.com"]')
        monkeypatch.setattr(settings, "BREVO_API_KEY", "test-key")
        monkeypatch.setattr(settings, "BREVO_SENDER_EMAIL", "info@gadgeto.com.ua")
        monkeypatch.setattr(settings, "BREVO_SENDER_NAME", "Gadgeto")
        client, context = _mock_http()
        with patch("app.services.email.httpx.Client", return_value=context) as m:
            result = send_catalog_sync_failure_email(
                run_id=7, status="FAILED", trigger="scheduler", failures=FAILURES,
                started_at=datetime(2026, 9, 3, 12, 0, 0),
                finished_at=datetime(2026, 9, 3, 12, 5, 0),
            )
        assert result is True
        m.assert_called_once()
        payload = client.post.call_args.kwargs["json"]
        assert payload["sender"] == {"email": "info@gadgeto.com.ua",
                                     "name": "Gadgeto"}
        assert [t["email"] for t in payload["to"]] == ["a@example.com",
                                                        "b@example.com"]
        assert "помилка" in payload["subject"]
        assert "#7" in payload["subject"]
        assert "itlink" in payload["htmlContent"]
        assert "feed download failed" in payload["textContent"]
        assert "03.09.2026 12:00:00" in payload["textContent"]
        url = client.post.call_args.args[0]
        assert url.endswith("/smtp/email")

    def test_http_error_returns_false(self, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAILS",
                            '["a@example.com"]')
        monkeypatch.setattr(settings, "BREVO_API_KEY", "test-key")
        client, context = _mock_http(is_success=False, status_code=500)
        with patch("app.services.email.httpx.Client", return_value=context):
            result = send_catalog_sync_failure_email(
                run_id=3, status="FAILED", trigger="scheduler", failures=FAILURES,
            )
        assert result is False

    def test_timeout_returns_false(self, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_NOTIFICATION_EMAILS",
                            '["a@example.com"]')
        monkeypatch.setattr(settings, "BREVO_API_KEY", "test-key")
        client, context = _mock_http()
        client.post.side_effect = httpx.TimeoutException("timeout")
        with patch("app.services.email.httpx.Client", return_value=context):
            result = send_catalog_sync_failure_email(
                run_id=4, status="FAILED", trigger="scheduler", failures=FAILURES,
            )
        assert result is False


# ── Failure rendering helpers ────────────────────────────────────────────────


class TestFailureRendering:
    def test_html_escapes_user_content(self):
        out = _failures_html([
            {"source": "supplier", "name": "<b>x</b>",
             "error": "<script>1</script>"},
        ])
        assert "<b>x</b>" not in out
        assert "&lt;b&gt;x&lt;/b&gt;" in out
        assert "<script>" not in out

    def test_text_lists_failures(self):
        out = _failures_text([
            {"source": "channel", "name": "rozetka", "error": "API 500"},
        ])
        assert "Платформа експорту: rozetka — API 500" in out

    def test_empty_failures_placeholder(self):
        assert "Деталі відсутні" in _failures_html([])
        assert "Деталі відсутні" in _failures_text([])


# ── Orchestrator hooks ───────────────────────────────────────────────────────


def _patch_state(monkeypatch, run: dict):
    """Patch the state functions used by the finalize tasks (no DB)."""
    finish = MagicMock()

    def _finish(run_id: int, status: str, error_details=None):
        run["status"] = status
        run["finished_at"] = datetime(2026, 9, 3, 13, 0, 0)

    finish.side_effect = _finish
    monkeypatch.setattr(state, "load_catalog_run",
                        MagicMock(side_effect=lambda run_id: dict(run)))
    monkeypatch.setattr(state, "finish_catalog_run", finish)
    monkeypatch.setattr(state, "append_run_log", MagicMock())


class TestAfterSupplierImportsNotification:
    def test_failed_imports_send_email(self, monkeypatch):
        run = {"id": 10, "status": state.RUN_RUNNING, "trigger": "scheduler",
               "started_at": datetime(2026, 9, 3, 12, 0, 0),
               "finished_at": None, "lock_token": "tok"}
        _patch_state(monkeypatch, run)
        monkeypatch.setattr(state, "resolve_enabled_channels", MagicMock())
        notify = MagicMock()
        monkeypatch.setattr("app.tasks.catalog_sync.send_catalog_sync_failure_email",
                            notify)
        monkeypatch.setattr("app.tasks.catalog_sync._release_run_lock", MagicMock())

        results = [
            {"supplier": "itlink", "status": "FAILED", "error": "boom"},
            {"supplier": "dclink", "status": "SUCCEEDED"},
        ]
        out = after_supplier_imports(results, 10)

        assert out["status"] == "FAILED"
        notify.assert_called_once()
        kwargs = notify.call_args.kwargs
        assert kwargs["status"] == state.RUN_FAILED
        assert kwargs["trigger"] == "scheduler"
        assert kwargs["failures"] == [
            {"source": "supplier", "name": "itlink", "status": "FAILED",
             "error": "boom"},
        ]

    def test_successful_imports_send_nothing(self, monkeypatch):
        run = {"id": 11, "status": state.RUN_RUNNING, "trigger": "scheduler",
               "started_at": None, "finished_at": None, "lock_token": "tok"}
        _patch_state(monkeypatch, run)
        monkeypatch.setattr(state, "resolve_enabled_channels",
                            MagicMock(return_value=[]))
        notify = MagicMock()
        monkeypatch.setattr("app.tasks.catalog_sync.send_catalog_sync_failure_email",
                            notify)
        monkeypatch.setattr("app.tasks.catalog_sync._release_run_lock", MagicMock())

        results = [{"supplier": "itlink", "status": "SUCCEEDED"},
                   {"supplier": "dclink", "status": "SUCCEEDED"}]
        out = after_supplier_imports(results, 11)

        assert out["status"] == state.RUN_SUCCEEDED
        notify.assert_not_called()


class TestAfterChannelExportsNotification:
    def test_partial_exports_send_email(self, monkeypatch):
        run = {"id": 12, "status": state.RUN_RUNNING, "trigger": "manual",
               "started_at": None, "finished_at": None, "lock_token": "tok"}
        _patch_state(monkeypatch, run)
        notify = MagicMock()
        monkeypatch.setattr("app.tasks.catalog_sync.send_catalog_sync_failure_email",
                            notify)
        monkeypatch.setattr("app.tasks.catalog_sync._release_run_lock", MagicMock())

        results = [
            {"channel": "rozetka", "status": "FAILED", "error": "API 500"},
            {"channel": "other", "status": "SUCCEEDED"},
        ]
        out = after_channel_exports(results, 12)

        assert out["status"] == state.RUN_PARTIAL
        notify.assert_called_once()
        kwargs = notify.call_args.kwargs
        assert kwargs["status"] == state.RUN_PARTIAL
        assert kwargs["trigger"] == "manual"
        assert kwargs["failures"] == [
            {"source": "channel", "name": "rozetka", "status": "FAILED",
             "error": "API 500"},
        ]

    def test_all_succeeded_send_nothing(self, monkeypatch):
        run = {"id": 13, "status": state.RUN_RUNNING, "trigger": "scheduler",
               "started_at": None, "finished_at": None, "lock_token": "tok"}
        _patch_state(monkeypatch, run)
        notify = MagicMock()
        monkeypatch.setattr("app.tasks.catalog_sync.send_catalog_sync_failure_email",
                            notify)
        monkeypatch.setattr("app.tasks.catalog_sync._release_run_lock", MagicMock())

        results = [{"channel": "rozetka", "status": "SUCCEEDED"}]
        out = after_channel_exports(results, 13)

        assert out["status"] == state.RUN_SUCCEEDED
        notify.assert_not_called()

    def test_email_error_never_breaks_run(self, monkeypatch):
        run = {"id": 14, "status": state.RUN_RUNNING, "trigger": "scheduler",
               "started_at": None, "finished_at": None, "lock_token": "tok"}
        _patch_state(monkeypatch, run)
        notify = MagicMock(side_effect=RuntimeError("brevo down"))
        monkeypatch.setattr("app.tasks.catalog_sync.send_catalog_sync_failure_email",
                            notify)
        monkeypatch.setattr("app.tasks.catalog_sync._release_run_lock", MagicMock())

        results = [{"channel": "rozetka", "status": "FAILED", "error": "x"}]
        out = after_channel_exports(results, 14)

        assert out["status"] == state.RUN_FAILED
        notify.assert_called_once()
