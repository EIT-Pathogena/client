import logging
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from pathogena import lib
from pathogena.constants import DEFAULT_HOST
from pathogena.errors import UnsupportedClientError
from pathogena.log_utils import httpx_hooks


@patch("httpx.Client.get")
@patch("pathogena.__version__", "1.0.0")
def test_check_new_version_available(
    mock_get: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test to check that a new version is available if it exists.

    Args:
        mock_get (MagicMock): Mocked `httpx.Client.get` method.
        caplog (pytest.LogCaptureFixture): Pytest fixture to capture log output.
    """
    caplog.set_level(logging.INFO)
    mock_get.return_value = httpx.Response(
        status_code=200, json={"info": {"version": "1.1.0"}}
    )
    lib.check_for_newer_version()
    assert "A new version of the EIT Pathogena CLI" in caplog.text


@patch("httpx.Client.get")
@patch("pathogena.__version__", "1.0.0")
def test_check_no_new_version_available(
    mock_get: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that no new version is available if request is latest.

    Args:
        mock_get (MagicMock): Mocked `httpx.Client.get` method.
        caplog (pytest.LogCaptureFixture): Pytest fixture to capture log output.
    """
    caplog.set_level(logging.INFO)
    mock_get.return_value = httpx.Response(
        status_code=200, json={"info": {"version": "1.0.0"}}
    )
    lib.check_for_newer_version()
    assert not caplog.text


@patch("httpx.Client.get")
@patch("pathogena.__version__", "1.0.1")
def test_check_version_compatibility(
    mock_get: MagicMock, caplog: pytest.LogCaptureFixture, test_host: str
) -> None:
    """Test to check whether two minor versions are compatible.

    Args:
        mock_get (MagicMock): Mocked `httpx.Client.get` method.
        caplog (pytest.LogCaptureFixture): Pytest fixture to capture log output.
    """
    mock_get.return_value = httpx.Response(status_code=200, json={"version": "1.0.0"})
    lib.check_version_compatibility(host=test_host)


@patch("httpx.Client.get")
@patch("pathogena.__version__", "1.0.0")
def test_fail_check_version_compatibility(
    mock_get: MagicMock, caplog: pytest.LogCaptureFixture, test_host: str
) -> None:
    """Test failure of version compatibility check.

    Args:
        mock_get (MagicMock): Mocked `httpx.Client.get` method.
        caplog (pytest.LogCaptureFixture): Pytest fixture to capture log output.
    """
    caplog.set_level(logging.INFO)
    mock_get.return_value = httpx.Response(status_code=200, json={"version": "1.0.1"})
    with pytest.raises(UnsupportedClientError):
        lib.check_version_compatibility(host=test_host)
        assert "is no longer supported" in caplog.text


@patch("httpx.Client.get")
@patch("pathogena.lib.get_access_token")
def test_get_balance(
    mock_token: MagicMock, mock_get: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test successfully getting the balance for a given account.

    Args:
        mock_token (MagicMock): Mocked `pathogena.lib.get_access_token` method.
        mock_get (MagicMock): Mocked `httpx.Client.get` method.
        caplog (pytest.LogCaptureFixture): Pytest fixture to capture log output.
    """
    caplog.set_level(logging.INFO)
    mock_token.return_value = "fake_token"
    mock_get.return_value = httpx.Response(status_code=200, text="1000")
    lib.get_credit_balance(host="fake_host")
    assert "Your remaining account balance is 1000 credits" in caplog.text


@patch("httpx.Client.get")
@patch("pathogena.lib.get_access_token")
def test_get_balance_failure(
    mock_token: MagicMock, mock_client_get: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test failure to get the account balance.

    Args:
        mock_token (MagicMock): Mocked `pathogena.lib.get_access_token` method.
        mock_client_get (MagicMock): Mocked `httpx.Client.get` method.
        caplog (pytest.LogCaptureFixture): Pytest fixture to capture log output.
    """
    mock_token.return_value = "fake_token"
    mock_client_get.return_value = httpx.Response(status_code=402)
    lib.get_credit_balance(host="fake_host")
    assert (
        "Your account doesn't have enough credits to fulfil the number of Samples in your Batch."
        in caplog.text
    )


@patch("pathogena.lib.httpx.Client")
def test_log_download_mapping_file_success(mock_client: MagicMock, caplog):
    """Test download csv logging called as expected"""

    batch_id = "batch123"
    file_name = "mapping"
    token = "tok-xyz"
    host = DEFAULT_HOST

    fake_client = MagicMock()

    # mock the context‐manager
    mock_client.return_value.__enter__.return_value = fake_client
    mock_client.return_value.__exit__.return_value = None

    # call
    lib.log_download_mapping_file_to_portal(
        batch_id=batch_id, file_name=file_name, token=token, host=host
    )

    # check called once
    assert mock_client.call_count == 1

    # check kwargs as expected
    _, kwargs = mock_client.call_args
    assert kwargs["event_hooks"] is httpx_hooks
    assert isinstance(kwargs["transport"], httpx.HTTPTransport)
    assert kwargs["timeout"] == 60


def make_dummy_batch():
    """
    Create a minimal UploadBatch-like object with one sample,
    so upload_batch doesn't blow up before our helper call.
    """
    sample = MagicMock(sample_name="test", amplicon_scheme="test_amplicon")
    batch = MagicMock(
        samples=[sample],
    )
    return batch


@patch("pathogena.lib.upload_utils.upload_fastq")
@patch("pathogena.lib.get_remote_sample_name", return_value="dummy_remote_sample")
@patch("pathogena.lib.log_download_mapping_file_to_portal")
@patch("pathogena.util.write_csv")
@patch("pathogena.lib.prepare_files")
@patch("pathogena.lib.create_batch_on_server")
@patch("pathogena.util.get_access_token", return_value="tok-123")
def test_upload_batch_calls_portal_logging_on_success(
    mock_token,
    mock_create,
    mock_prepare,
    mock_write_csv,
    mock_logger,
    mock_get_remote,
    mock_upload_fastq,
    caplog,
):
    # mock create_batch_on_server to return dummy IDs
    dummy_batch_id = uuid4()
    dummy_local_name = "local"
    dummy_remote_name = "remote"
    dummy_legacy_id = uuid4()
    mock_create.return_value = (
        dummy_batch_id,
        dummy_local_name,
        dummy_remote_name,
        dummy_legacy_id,
    )

    # mock prepare _files to give upload session
    mock_prepare.return_value = {"uploadSession": {}, "files": [], "other": {}}

    batch = make_dummy_batch()

    # call upload batch
    lib.upload_batch(batch=batch, host="https://test.com")

    # assert called as expected
    mock_logger.assert_called_once_with(
        str(dummy_batch_id),
        dummy_remote_name,
        "tok-123",
        "https://test.com",
    )
    # no log levels of warning or higher
    assert not [rec for rec in caplog.records if rec.levelno >= logging.WARNING]


@patch("pathogena.lib.upload_utils.upload_fastq")
@patch("pathogena.lib.get_remote_sample_name", return_value="dummy_remote")
@patch(
    "pathogena.lib.log_download_mapping_file_to_portal",
    side_effect=Exception("noooooo!"),
)
@patch("pathogena.util.write_csv")
@patch("pathogena.lib.prepare_files")
@patch("pathogena.lib.create_batch_on_server")
@patch("pathogena.util.get_access_token", return_value="tok-123")
def test_upload_batch_portal_logging_failure(
    mock_token,
    mock_create,
    mock_prepare,
    mock_write_csv,
    mock_logger,
    mock_get_remote,
    mock_upload_fastq,
    caplog,
):
    # mock create_batch_on_server to return dummy IDs
    dummy_batch_id = uuid4()
    dummy_local_name = "local"
    dummy_remote_name = "remote"
    dummy_legacy_id = uuid4()

    mock_create.return_value = (
        dummy_batch_id,
        dummy_local_name,
        dummy_remote_name,
        dummy_legacy_id,
    )
    # mock prepare _files to give upload session
    mock_prepare.return_value = {
        "uploadSession": {},
        "files": [],
        "other": {},
    }

    batch = make_dummy_batch()

    # call upload batch
    lib.upload_batch(batch=batch, host="https://test.com")

    # assert called the logger
    mock_logger.assert_called_once_with(
        str(dummy_batch_id),
        dummy_remote_name,
        "tok-123",
        "https://test.com",
    )

    # assert logged that failed to log in portal
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any(
        "Could not log mapping-file download to portal" in r.message for r in warnings
    )
