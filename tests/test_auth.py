import logging
from unittest import mock

import httpx
import pytest

from pathogena import __version__
from pathogena.tasks import authenticate

DEFAULT_HOST = "dummy_default_host.com"


@pytest.fixture
def mock_httpx_client(mocker):
    """Mocks httpx.Client and its post method."""
    mock_response = mocker.MagicMock(spec=httpx.Response)
    mock_client = mocker.MagicMock(spec=httpx.Client)
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.post.return_value = mock_response

    mocker.patch("httpx.Client", return_value=mock_client)
    return mock_response


@pytest.fixture
def mock_user_input(mocker):
    """Mocks builtins.input and getpass.getpass."""
    mocker.patch("pathogena.tasks.authentication.input", return_value="testuser")
    mocker.patch("pathogena.tasks.authentication.getpass", return_value="testpassword")


def test_authenticate_upgrade_required(mock_httpx_client, mock_user_input, caplog):
    """Tests the path where the client requires an upgrade (426 status code)."""
    caplog.set_level(logging.ERROR)

    mock_httpx_client.status_code = httpx.codes.UPGRADE_REQUIRED
    mock_httpx_client.text = "Please update your client."

    with pytest.raises(ValueError, match="Client update required."):
        authenticate()

    assert "Client update required: Your client version is too old." in caplog.text

    mock_client_instance = httpx.Client.return_value  # type: ignore
    mock_client_instance.post.assert_called_once()
    _, kwargs = mock_client_instance.post.call_args
    assert kwargs["headers"] == {"X-CLIENT-VERSION": __version__}


def test_authenticate_http_error(mock_httpx_client, mock_user_input, caplog):
    """Tests the path where raise_for_status is called for other HTTP errors (e.g., 401)."""
    caplog.set_level(logging.INFO)

    mock_httpx_client.status_code = httpx.codes.UNAUTHORIZED
    mock_httpx_client.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Unauthorized",
        request=mock.MagicMock(spec=httpx.Request),
        response=mock_httpx_client,
    )

    with pytest.raises(httpx.HTTPStatusError, match="Unauthorized"):
        authenticate()

    assert "Authenticating with" in caplog.text
    assert "Client update required:" not in caplog.text


def test_authenticate_success(mock_httpx_client, mock_user_input, caplog):
    """Tests the successful authentication path (200 OK)."""
    caplog.set_level(logging.INFO)

    mock_httpx_client.status_code = httpx.codes.OK
    auth_token_data = {
        "access_token": "mock_token",
        "expires_in": 3600,  # 1 hour in seconds
        "token_type": "Bearer",
    }
    mock_httpx_client.json.return_value = auth_token_data

    authenticate(host="test.example.com")

    # Assertions

    mock_client_instance = httpx.Client.return_value  # type: ignore
    mock_client_instance.post.assert_called_once_with(
        "https://test.example.com/api/v1/auth/token",
        json={"username": "testuser", "password": "testpassword"},
        follow_redirects=True,
        headers={"X-CLIENT-VERSION": __version__},
    )

    assert "Authenticating with test.example.com" in caplog.text
    assert "Authenticated" in caplog.text
