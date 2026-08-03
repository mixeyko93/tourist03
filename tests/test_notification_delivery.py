import os
import smtplib
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest.mock import MagicMock, patch

from scripts import smtp_gate
from tourist03.services.notification_delivery import (
    EmailDeliveryUnavailable,
    _send_email,
    deliver_pending_email_notifications,
)
from tourist03.settings import Settings
from tourist03.workers.notification_outbox import process_once
from tourist03.workers import notification_outbox


class NotificationDeliveryTests(unittest.TestCase):
    def event(self):
        return {
            "id": 17,
            "recipient_address": "owner@example.org",
            "event_type": "owner_account_created",
            "title": "Добро пожаловать",
            "body": "Кабинет готов.",
        }

    @staticmethod
    def client_context():
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = None
        client.send_message.return_value = {}
        return client

    def test_email_delivery_disabled_does_not_read_or_mutate_outbox(self):
        settings = Settings(environment="test", feature_email_delivery=False)
        with patch(
            "tourist03.services.notification_delivery.notification_repo.list_pending_email_notifications"
        ) as pending:
            self.assertEqual(
                deliver_pending_email_notifications(settings=settings),
                0,
            )
        pending.assert_not_called()

    def test_production_secret_file_aliases_select_ssl_465(self):
        with patch.dict(
            os.environ,
            {
                "SMTP_USERNAME": "alias-user",
                "SMTP_FROM_EMAIL": "robot@example.org",
                "SMTP_USE_SSL": "true",
                "SMTP_USE_STARTTLS": "false",
                "TURNSTILE_SITE_KEY": "site-key",
                "TURNSTILE_SECRET_KEY": "secret-key",
            },
        ):
            settings = Settings(_env_file=None, environment="test")
        self.assertEqual(settings.smtp_user, "alias-user")
        self.assertEqual(settings.smtp_from, "robot@example.org")
        self.assertEqual(settings.smtp_security, "ssl")
        self.assertEqual(settings.submission_captcha_site_key, "site-key")
        self.assertEqual(settings.submission_captcha_secret, "secret-key")

    def test_smtp_ssl_uses_direct_tls_auth_and_headers(self):
        client = self.client_context()
        settings = Settings(
            environment="test",
            feature_email_delivery=True,
            smtp_host="smtp.example",
            smtp_port=465,
            smtp_user="robot",
            smtp_password="private-password",
            smtp_from="robot@example.org",
            smtp_from_name="Туристика",
            smtp_reply_to="support@example.org",
            smtp_security="ssl",
        )
        with patch(
            "tourist03.services.notification_delivery.smtplib.SMTP_SSL",
            return_value=client,
        ) as smtp_ssl, patch(
            "tourist03.services.notification_delivery.smtplib.SMTP"
        ) as smtp:
            _send_email(self.event(), settings)
        smtp.assert_not_called()
        smtp_ssl.assert_called_once()
        client.login.assert_called_once_with("robot", "private-password")
        message = client.send_message.call_args.args[0]
        self.assertEqual(message["Reply-To"], "support@example.org")
        self.assertIn("Туристика", str(message["From"]))

    def test_smtp_starttls_upgrades_before_auth(self):
        client = self.client_context()
        settings = Settings(
            environment="test",
            feature_email_delivery=True,
            smtp_host="smtp.example",
            smtp_port=587,
            smtp_user="robot",
            smtp_password="private-password",
            smtp_from="robot@example.org",
            smtp_security="starttls",
        )
        with patch(
            "tourist03.services.notification_delivery.smtplib.SMTP",
            return_value=client,
        ) as smtp:
            _send_email(self.event(), settings)
        smtp.assert_called_once()
        client.starttls.assert_called_once()
        self.assertEqual(client.ehlo.call_count, 2)
        client.login.assert_called_once_with("robot", "private-password")

    def test_owner_reset_uses_lk_fragment_and_removes_token_from_query(self):
        client = self.client_context()
        settings = Settings(
            environment="test",
            feature_email_delivery=True,
            smtp_host="smtp.example",
            smtp_port=465,
            smtp_from="robot@example.org",
            smtp_security="ssl",
            public_base_url="https://turistika.pro",
            owner_base_url="https://lk.turistika.pro",
        )
        event = {
            **self.event(),
            "event_type": "owner_password_reset_requested",
            "action_url": "/owner",
            "action_payload": {
                "reset_id": 11,
                "owner_id": 22,
                "expires_at": (
                    datetime.now(timezone.utc) + timedelta(minutes=30)
                ).isoformat(),
            },
        }
        with (
            patch(
                "tourist03.services.notification_delivery.smtplib.SMTP_SSL",
                return_value=client,
            ),
            patch(
                "tourist03.services.notification_delivery.owner_reset_token_for",
                return_value="safe-reset-token",
            ),
        ):
            _send_email(event, settings)
        body = client.send_message.call_args.args[0].get_content()
        self.assertIn(
            "https://lk.turistika.pro/owner#reset=safe-reset-token",
            body,
        )
        self.assertNotIn("?token=", body)
        self.assertNotIn("https://turistika.pro/owner", body)

    def test_smtp_plain_does_not_start_tls(self):
        client = self.client_context()
        settings = Settings(
            environment="test",
            feature_email_delivery=True,
            smtp_host="localhost",
            smtp_port=1025,
            smtp_from="robot@example.org",
            smtp_security="plain",
        )
        with patch(
            "tourist03.services.notification_delivery.smtplib.SMTP",
            return_value=client,
        ):
            _send_email(self.event(), settings)
        client.starttls.assert_not_called()
        client.send_message.assert_called_once()

    def test_malformed_recipient_is_rejected_before_smtp(self):
        settings = Settings(
            environment="test",
            feature_email_delivery=True,
            smtp_host="smtp.example",
            smtp_from="robot@example.org",
        )
        event = {
            **self.event(),
            "recipient_address": "owner@example.org\nBcc: attacker@example.org",
        }
        with patch(
            "tourist03.services.notification_delivery.smtplib.SMTP"
        ) as smtp:
            with self.assertRaises(EmailDeliveryUnavailable):
                _send_email(event, settings)
        smtp.assert_not_called()

    def test_refused_recipient_response_is_not_treated_as_success(self):
        client = self.client_context()
        client.send_message.return_value = {
            "owner@example.org": (550, b"recipient refused")
        }
        settings = Settings(
            environment="test",
            feature_email_delivery=True,
            smtp_host="smtp.example",
            smtp_from="robot@example.org",
            smtp_security="starttls",
        )
        with patch(
            "tourist03.services.notification_delivery.smtplib.SMTP",
            return_value=client,
        ):
            with self.assertRaises(smtplib.SMTPRecipientsRefused):
                _send_email(self.event(), settings)

    def test_malformed_smtp_response_is_recorded_for_retry_without_secret(self):
        event = {
            **self.event(),
            "claim_token": "email-claim-token",
            "attempts": 3,
        }
        settings = Settings(
            environment="test",
            feature_email_delivery=True,
            smtp_host="smtp.example",
            smtp_user="robot",
            smtp_password="private-password",
            smtp_from="robot@example.org",
        )
        with (
            patch(
                "tourist03.services.notification_delivery.notification_repo.claim_pending_email_notifications",
                return_value=[event],
            ),
            patch(
                "tourist03.services.notification_delivery._send_email",
                side_effect=smtplib.SMTPDataError(
                    451,
                    b"malformed response private-password",
                ),
            ),
            patch(
                "tourist03.services.notification_delivery.notification_repo.mark_claimed_email_notification_failed",
                return_value=True,
            ) as failed,
        ):
            self.assertEqual(
                deliver_pending_email_notifications(settings=settings),
                0,
            )
        error_message = failed.call_args.args[2]
        self.assertIn("451", error_message)
        self.assertNotIn(settings.smtp_password, error_message)

    def test_retry_uses_stable_message_id_for_provider_deduplication(self):
        settings = Settings(
            environment="test",
            feature_email_delivery=True,
            smtp_host="smtp.example",
            smtp_from="robot@example.org",
            smtp_security="starttls",
            session_secret_key="stable-test-session-secret",
        )
        event = {**self.event(), "dedupe_key": "email:stable:17"}
        first_client = self.client_context()
        second_client = self.client_context()
        with patch(
            "tourist03.services.notification_delivery.smtplib.SMTP",
            side_effect=[first_client, second_client],
        ):
            first = _send_email(event, settings)
            second = _send_email(event, settings)
        self.assertEqual(first, second)
        self.assertEqual(
            first_client.send_message.call_args.args[0]["Message-ID"],
            second_client.send_message.call_args.args[0]["Message-ID"],
        )

    def test_worker_keeps_cleanup_independent_from_email_gate(self):
        settings = Settings(
            environment="test",
            feature_email_delivery=False,
            submission_cleanup_enabled=True,
        )
        with patch(
            "tourist03.workers.notification_outbox.deliver_pending_email_notifications",
            return_value=0,
        ) as deliver, patch(
            "tourist03.workers.notification_outbox.cleanup_expired_submission_uploads",
            return_value=3,
        ) as cleanup:
            self.assertEqual(process_once(settings), (0, 3))
        deliver.assert_called_once_with(settings=settings)
        cleanup.assert_called_once_with(settings=settings)

    def test_cleanup_only_cli_never_reads_email_queue(self):
        settings = Settings(
            environment="test",
            feature_email_delivery=True,
            submission_cleanup_enabled=True,
        )
        with patch.object(
            notification_outbox,
            "get_settings",
            return_value=settings,
        ), patch.object(
            notification_outbox,
            "deliver_pending_email_notifications",
        ) as deliver, patch.object(
            notification_outbox,
            "cleanup_expired_submission_uploads",
            return_value=2,
        ) as cleanup:
            self.assertEqual(notification_outbox.main(["--cleanup-only"]), 0)
        deliver.assert_not_called()
        cleanup.assert_called_once_with(settings=settings)

    def test_smtp_gate_runs_direct_ssl_auth_and_send_without_outbox(self):
        client = self.client_context()
        settings = Settings(
            environment="test",
            smtp_host="smtp.example",
            smtp_port=465,
            smtp_user="robot",
            smtp_password="do-not-print-this-password",
            smtp_from="robot@example.org",
            smtp_test_email="acceptance@example.org",
            smtp_security="ssl",
        )
        output = StringIO()
        with patch(
            "scripts.smtp_gate.socket.getaddrinfo",
            return_value=[object()],
        ), patch(
            "scripts.smtp_gate.smtplib.SMTP_SSL",
            return_value=client,
        ), redirect_stdout(output):
            self.assertEqual(smtp_gate.run_gate(settings), 0)
        rendered = output.getvalue()
        self.assertIn("stage=send status=ok", rendered)
        self.assertNotIn(settings.smtp_password, rendered)
        client.login.assert_called_once_with("robot", settings.smtp_password)
        client.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
