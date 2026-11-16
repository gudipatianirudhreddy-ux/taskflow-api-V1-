import base64
from email import message_from_bytes, policy
import importlib.util
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError

# Dynamically import the real email_service module to bypass test conftest mock if present
_module_path = (
    Path(__file__).resolve().parent.parent / "app" / "services" / "email_service.py"
)
_spec = importlib.util.spec_from_file_location(
    "app.services.email_service_real", str(_module_path)
)
email_service = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(email_service)

send_group_invitation = email_service.send_group_invitation


@pytest.fixture
def gmail_env(monkeypatch):
    """Set up valid Gmail API environment variables."""
    monkeypatch.setenv("GMAIL_SENDER_EMAIL", "sender@example.com")
    monkeypatch.setenv("GMAIL_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GMAIL_CLIENT_SECRET", "test-client-secret-xyz")
    monkeypatch.setenv("GMAIL_REFRESH_TOKEN", "1//test-refresh-token-abc")


class TestGmailServiceSending:
    @patch.object(email_service, "googleapiclient")
    @patch.object(email_service, "Request")
    @patch.object(email_service, "Credentials")
    def test_send_group_invitation_success(
        self, mock_credentials_cls, mock_request_cls, mock_googleapiclient, gmail_env
    ):
        mock_creds = MagicMock()
        mock_credentials_cls.return_value = mock_creds

        mock_request_instance = MagicMock()
        mock_request_cls.return_value = mock_request_instance

        mock_service = MagicMock()
        mock_googleapiclient.discovery.build.return_value = mock_service
        mock_send = MagicMock()
        mock_service.users().messages().send.return_value = mock_send
        mock_send.execute.return_value = {"id": "msg_12345", "threadId": "th_67890"}

        res = send_group_invitation(
            to_email="recipient@example.com",
            inviter_email="inviter@example.com",
            group_name="Design Team",
            accept_url="https://app.example.com/invitations/token_abc",
        )

        assert res == {"id": "msg_12345", "threadId": "th_67890"}

        # 1. Verify Credentials initialization
        mock_credentials_cls.assert_called_once_with(
            token=None,
            refresh_token="1//test-refresh-token-abc",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test-client-id.apps.googleusercontent.com",
            client_secret="test-client-secret-xyz",
            scopes=["https://www.googleapis.com/auth/gmail.send"],
        )

        # 2. Verify Request creation and credentials refresh
        mock_request_cls.assert_called_once()
        mock_creds.refresh.assert_called_once_with(mock_request_instance)

        # 3. Verify Gmail API client build
        mock_googleapiclient.discovery.build.assert_called_once_with(
            "gmail", "v1", credentials=mock_creds, cache_discovery=False
        )

        # 4. Verify message sending
        mock_service.users().messages().send.assert_called_once()
        call_kwargs = mock_service.users().messages().send.call_args[1]
        assert call_kwargs["userId"] == "me"
        assert "raw" in call_kwargs["body"]

    @patch.object(email_service, "googleapiclient")
    @patch.object(email_service, "Request")
    @patch.object(email_service, "Credentials")
    def test_message_headers_and_content(
        self, mock_credentials_cls, mock_request_cls, mock_googleapiclient, gmail_env
    ):
        mock_creds = MagicMock()
        mock_credentials_cls.return_value = mock_creds
        mock_service = MagicMock()
        mock_googleapiclient.discovery.build.return_value = mock_service
        mock_send = MagicMock()
        mock_service.users().messages().send.return_value = mock_send
        mock_send.execute.return_value = {"id": "msg_abc"}

        send_group_invitation(
            to_email="colleague@example.com",
            inviter_email="alice@example.com",
            group_name="Frontend Guild",
            accept_url="https://myapp.com/invite/tok123",
        )

        call_kwargs = mock_service.users().messages().send.call_args[1]
        raw_b64 = call_kwargs["body"]["raw"]

        # Decode the URL-safe base64 string into EmailMessage
        raw_bytes = base64.urlsafe_b64decode(raw_b64.encode("utf-8"))
        msg = message_from_bytes(raw_bytes, policy=policy.default)

        # Header checks
        assert msg["From"] == "sender@example.com"
        assert msg["To"] == "colleague@example.com"
        assert msg["Subject"] == "You're invited to join Frontend Guild"

        # Content checks: multipart alternative with text/plain and text/html
        assert msg.is_multipart()
        parts = list(msg.walk())
        content_types = [p.get_content_type() for p in parts]
        assert "text/plain" in content_types
        assert "text/html" in content_types

        # Plain text verification
        plain_part = next(p for p in parts if p.get_content_type() == "text/plain")
        plain_content = plain_part.get_content()
        assert "alice@example.com" in plain_content
        assert "Frontend Guild" in plain_content
        assert "https://myapp.com/invite/tok123" in plain_content
        assert "expire in 7 days" in plain_content

        # HTML verification
        html_part = next(p for p in parts if p.get_content_type() == "text/html")
        html_content = html_part.get_content()
        assert "<h2>You're invited to join Frontend Guild</h2>" in html_content
        assert "alice@example.com" in html_content
        assert 'href="https://myapp.com/invite/tok123"' in html_content
        assert "Please note: This invitation link will expire in 7 days." in html_content


class TestGmailConfigurationErrors:
    @pytest.mark.parametrize(
        "missing_var",
        [
            "GMAIL_SENDER_EMAIL",
            "GMAIL_CLIENT_ID",
            "GMAIL_CLIENT_SECRET",
            "GMAIL_REFRESH_TOKEN",
        ],
    )
    def test_missing_single_env_var_raises_value_error(self, monkeypatch, missing_var, gmail_env):
        monkeypatch.delenv(missing_var, raising=False)
        with pytest.raises(ValueError) as exc_info:
            send_group_invitation(
                to_email="test@example.com",
                inviter_email="inviter@example.com",
                group_name="Group A",
                accept_url="https://example.com/invite",
            )
        err_msg = str(exc_info.value)
        assert "Missing required Gmail API environment variable(s)" in err_msg
        assert missing_var in err_msg
        # Ensure secret values are not leaked in exception
        assert "test-client-secret-xyz" not in err_msg
        assert "1//test-refresh-token-abc" not in err_msg

    def test_missing_all_env_vars_raises_value_error(self, monkeypatch):
        for var in [
            "GMAIL_SENDER_EMAIL",
            "GMAIL_CLIENT_ID",
            "GMAIL_CLIENT_SECRET",
            "GMAIL_REFRESH_TOKEN",
        ]:
            monkeypatch.delenv(var, raising=False)

        with pytest.raises(ValueError) as exc_info:
            send_group_invitation(
                to_email="test@example.com",
                inviter_email="inviter@example.com",
                group_name="Group A",
                accept_url="https://example.com/invite",
            )
        err_msg = str(exc_info.value)
        assert "Missing required Gmail API environment variable(s)" in err_msg
        for var in [
            "GMAIL_SENDER_EMAIL",
            "GMAIL_CLIENT_ID",
            "GMAIL_CLIENT_SECRET",
            "GMAIL_REFRESH_TOKEN",
        ]:
            assert var in err_msg


class TestGmailApiErrorHandling:
    @patch.object(email_service, "Request")
    @patch.object(email_service, "Credentials")
    def test_credential_refresh_failure_propagates(
        self, mock_credentials_cls, mock_request_cls, gmail_env, caplog
    ):
        mock_creds = MagicMock()
        mock_credentials_cls.return_value = mock_creds
        mock_creds.refresh.side_effect = RefreshError("Failed to refresh token: invalid_grant")

        with pytest.raises(RefreshError) as exc_info:
            send_group_invitation(
                to_email="test@example.com",
                inviter_email="inviter@example.com",
                group_name="Alpha",
                accept_url="https://example.com/invite",
            )

        assert "invalid_grant" in str(exc_info.value)
        # Ensure secrets are not in captured logs
        assert "test-client-secret-xyz" not in caplog.text
        assert "1//test-refresh-token-abc" not in caplog.text

    @patch.object(email_service, "googleapiclient")
    @patch.object(email_service, "Request")
    @patch.object(email_service, "Credentials")
    def test_send_api_http_error_propagates(
        self, mock_credentials_cls, mock_request_cls, mock_googleapiclient, gmail_env, caplog
    ):
        mock_creds = MagicMock()
        mock_credentials_cls.return_value = mock_creds
        mock_service = MagicMock()
        mock_googleapiclient.discovery.build.return_value = mock_service
        mock_send = MagicMock()
        mock_service.users().messages().send.return_value = mock_send

        # Simulate Gmail API 400 or 500 HttpError
        resp = MagicMock(status=400, reason="Bad Request")
        mock_send.execute.side_effect = HttpError(resp=resp, content=b'{"error": {"message": "Invalid recipient"}}')

        with pytest.raises(HttpError) as exc_info:
            send_group_invitation(
                to_email="invalid-email",
                inviter_email="inviter@example.com",
                group_name="Alpha",
                accept_url="https://example.com/invite",
            )

        assert "Invalid recipient" in str(exc_info.value)
        # Ensure secrets are not in logs
        assert "test-client-secret-xyz" not in caplog.text
        assert "1//test-refresh-token-abc" not in caplog.text


class TestGroupInvitationRouteBehavior:
    def test_invite_success_calls_email_and_persists_invitation(
        self, auth_client_user1, user2, db, monkeypatch
    ):
        mock_send = MagicMock(return_value={"id": "msg_ok"})
        monkeypatch.setattr("app.routes.groups.send_group_invitation", mock_send)

        group_res = auth_client_user1.post(
            "/groups/", json={"name": "Route Test Group", "description": "Test"}
        )
        assert group_res.status_code == 201
        group_id = group_res.json()["id"]

        invite_res = auth_client_user1.post(
            f"/groups/{group_id}/invite", json={"email": user2.email}
        )
        assert invite_res.status_code == 201
        token = invite_res.json()["token"]

        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert kwargs["to_email"] == user2.email
        assert kwargs["group_name"] == "Route Test Group"
        assert token in kwargs["accept_url"]

        from app import models
        saved_invite = db.query(models.GroupInvitation).filter_by(token=token).first()
        assert saved_invite is not None
        assert saved_invite.email == user2.email

    def test_invite_failure_deletes_invitation_and_returns_500(
        self, auth_client_user1, user2, db, monkeypatch
    ):
        mock_send = MagicMock(side_effect=RuntimeError("Gmail API service unavailable"))
        monkeypatch.setattr("app.routes.groups.send_group_invitation", mock_send)

        group_res = auth_client_user1.post(
            "/groups/", json={"name": "Fail Test Group", "description": "Test"}
        )
        group_id = group_res.json()["id"]

        invite_res = auth_client_user1.post(
            f"/groups/{group_id}/invite", json={"email": user2.email}
        )
        assert invite_res.status_code == 500
        assert "Gmail API service unavailable" in invite_res.json()["detail"]

        from app import models
        saved_invite = db.query(models.GroupInvitation).filter_by(group_id=group_id).first()
        assert saved_invite is None
