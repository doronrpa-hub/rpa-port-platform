"""Tests for TaskYam authentication flow — NeedToChangePassword + IsSfaRequired.

Session 110: TaskYamClient.login() now handles 3 paths:
  1. Direct success (IsSuccess=true)
  2. Password change required (NeedToChangePassword=true)
  3. Second factor required (IsSfaRequired=true)
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from lib.tracker import TaskYamClient


def _make_secret(overrides=None):
    secrets = {
        "TASKYAM_USERNAME": "RCBRPA",
        "TASKYAM_PASSWORD": "testpass123",
    }
    if overrides:
        secrets.update(overrides)
    return lambda name: secrets.get(name)


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


class TestLoginDirectSuccess:
    def test_happy_path(self):
        resp = _mock_response({
            "IsSuccess": True,
            "Token": "abc123",
            "Message": "",
            "NeedToChangePassword": False,
            "IsSfaRequired": False,
        })
        with patch("requests.post", return_value=resp):
            client = TaskYamClient(_make_secret())
            assert client.login() is True
            assert client.token == "abc123"

    def test_stores_login_message(self):
        resp = _mock_response({
            "IsSuccess": False,
            "Token": None,
            "Message": "משתמש לא פעיל",
            "NeedToChangePassword": False,
            "IsSfaRequired": False,
            "InvalidLogins": 1,
        })
        with patch("requests.post", return_value=resp):
            client = TaskYamClient(_make_secret())
            assert client.login() is False
            assert client.login_message == "משתמש לא פעיל"

    def test_missing_credentials(self):
        client = TaskYamClient(lambda name: None)
        with patch("requests.post") as mock_post:
            assert client.login() is False
            mock_post.assert_not_called()

    def test_network_error(self):
        with patch("requests.post", side_effect=Exception("timeout")):
            client = TaskYamClient(_make_secret())
            assert client.login() is False


class TestNeedToChangePassword:
    def test_changes_password_and_updates_secret(self):
        # Login returns NeedToChangePassword=true with a token
        login_resp = _mock_response({
            "IsSuccess": False,
            "Token": "change-token",
            "Message": "נדרש שינוי סיסמא",
            "NeedToChangePassword": True,
            "IsSfaRequired": False,
        })
        # ChangePassword succeeds
        change_resp = _mock_response({
            "IsSuccess": True,
            "Token": "new-session-token",
        })

        call_count = [0]

        def mock_post(url, **kwargs):
            call_count[0] += 1
            if "Login" in url:
                return login_resp
            if "ChangePassword" in url:
                return change_resp
            return _mock_response({}, 404)

        with patch("requests.post", side_effect=mock_post):
            with patch.object(TaskYamClient, "_update_secret") as mock_update:
                client = TaskYamClient(_make_secret())
                result = client.login()

        assert result is True
        assert client.token == "new-session-token"
        # Should have called _update_secret with new password
        mock_update.assert_called_once()
        args = mock_update.call_args[0]
        assert args[0] == "TASKYAM_PASSWORD"
        assert len(args[1]) == 16  # Generated password length

    def test_change_password_api_fails(self):
        login_resp = _mock_response({
            "IsSuccess": False,
            "Token": "change-token",
            "NeedToChangePassword": True,
            "IsSfaRequired": False,
        })
        change_resp = _mock_response({
            "IsSuccess": False,
            "Message": "Password too weak",
        })

        def mock_post(url, **kwargs):
            if "Login" in url:
                return login_resp
            return change_resp

        with patch("requests.post", side_effect=mock_post):
            client = TaskYamClient(_make_secret())
            assert client.login() is False
            assert client.token is None

    def test_no_token_skips_password_change(self):
        """NeedToChangePassword without a Token → fail (can't call ChangePassword)."""
        login_resp = _mock_response({
            "IsSuccess": False,
            "Token": None,
            "NeedToChangePassword": True,
            "IsSfaRequired": False,
            "InvalidLogins": 1,
        })
        with patch("requests.post", return_value=login_resp):
            client = TaskYamClient(_make_secret())
            assert client.login() is False


class TestSecondFactor:
    def test_sfa_waits_for_code_in_firestore(self):
        login_resp = _mock_response({
            "IsSuccess": False,
            "Token": "sfa-token",
            "NeedToChangePassword": False,
            "IsSfaRequired": True,
            "MaskedMobile": "054***789",
        })
        verify_resp = _mock_response({
            "IsSuccess": True,
            "Token": "verified-token",
        })

        def mock_post(url, **kwargs):
            if "Login" in url:
                return login_resp
            if "VerifySecondFactor" in url:
                return verify_resp
            return _mock_response({}, 404)

        # Mock Firestore: pending doc gets code "123456" on first read
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"code": "123456", "status": "waiting_for_code"}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

        with patch("requests.post", side_effect=mock_post):
            with patch("firebase_admin.firestore.client", return_value=mock_db):
                with patch("time.sleep"):  # Don't actually sleep
                    client = TaskYamClient(_make_secret())
                    result = client.login()

        assert result is True
        assert client.token == "verified-token"

    def test_sfa_timeout_no_code(self):
        login_resp = _mock_response({
            "IsSuccess": False,
            "Token": "sfa-token",
            "NeedToChangePassword": False,
            "IsSfaRequired": True,
            "MaskedMobile": "054***789",
        })

        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"code": "", "status": "waiting_for_code"}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

        with patch("requests.post", return_value=login_resp):
            with patch("firebase_admin.firestore.client", return_value=mock_db):
                with patch("time.sleep"):
                    client = TaskYamClient(_make_secret())
                    result = client.login()

        assert result is False

    def test_sfa_verify_fails(self):
        login_resp = _mock_response({
            "IsSuccess": False,
            "Token": "sfa-token",
            "NeedToChangePassword": False,
            "IsSfaRequired": True,
        })
        verify_resp = _mock_response({
            "IsSuccess": False,
            "Message": "Invalid code",
        })

        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"code": "999999"}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

        def mock_post(url, **kwargs):
            if "Login" in url:
                return login_resp
            return verify_resp

        with patch("requests.post", side_effect=mock_post):
            with patch("firebase_admin.firestore.client", return_value=mock_db):
                with patch("time.sleep"):
                    client = TaskYamClient(_make_secret())
                    assert client.login() is False

    def test_no_firestore_fails_gracefully(self):
        login_resp = _mock_response({
            "IsSuccess": False,
            "Token": "sfa-token",
            "NeedToChangePassword": False,
            "IsSfaRequired": True,
        })
        with patch("requests.post", return_value=login_resp):
            with patch("firebase_admin.firestore.client", side_effect=ImportError):
                client = TaskYamClient(_make_secret())
                assert client.login() is False


class TestGetWithTokenExpiry:
    def test_401_logs_expiry_warning(self, capsys):
        resp = _mock_response({}, status_code=401)
        with patch("requests.get", return_value=resp):
            client = TaskYamClient(_make_secret())
            client.token = "expired-token"
            result = client._get("api/test")
        assert result is None
        captured = capsys.readouterr()
        assert "token may be expired" in captured.out

    def test_403_logs_sfa_warning(self, capsys):
        resp = _mock_response({}, status_code=403)
        with patch("requests.get", return_value=resp):
            client = TaskYamClient(_make_secret())
            client.token = "sfa-incomplete-token"
            result = client._get("api/test")
        assert result is None
        captured = capsys.readouterr()
        assert "SFA incomplete" in captured.out


class TestLoginResponseStructure:
    """Test that we handle the full Login response structure from live API probing."""

    def test_user_not_active(self):
        """Live response: 'משתמש לא פעיל' (User not active)."""
        resp = _mock_response({
            "IsSuccess": False,
            "Message": "משתמש לא פעיל",
            "Token": None,
            "NeedToChangePassword": False,
            "IsSfaRequired": False,
            "InvalidLogins": 1,
            "InvalidLoginType": 0,
            "MaskedMobile": None,
            "MaskedEmail": None,
        })
        with patch("requests.post", return_value=resp):
            client = TaskYamClient(_make_secret())
            assert client.login() is False
            assert "לא פעיל" in client.login_message

    def test_wrong_credentials(self):
        """Live response: 'שם משתמש או סיסמא אינם תקינים'."""
        resp = _mock_response({
            "IsSuccess": False,
            "Message": "שם משתמש או סיסמא אינם תקינים",
            "Token": None,
            "NeedToChangePassword": False,
            "IsSfaRequired": False,
        })
        with patch("requests.post", return_value=resp):
            client = TaskYamClient(_make_secret())
            assert client.login() is False
