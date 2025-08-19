import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from gpas import lib
from gpas.errors import UnsupportedClientError
from gpas.lib import upload_batch
from gpas.models import UploadBatch, UploadSample


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


@patch("gpas.lib.get_access_token", return_value="mock_valid_token")
@patch("gpas.lib.get_token_path", return_value=Path("/mock/path/to/token.json"))
@patch("pathlib.Path.read_text", return_value='{"access_token": "mock_valid_token"}')
@patch("gpas.lib.create_batch_on_server")
@patch("gpas.lib.prepare_files")
@patch("gpas.lib.upload_utils.upload_fastq")
@patch("gpas.lib.util.write_csv")
def test_upload_batch_success(
    mock_write_csv,
    mock_upload_fastq,
    mock_prepare_files,
    mock_create_batch_on_server,
    mock_read_text,
    mock_token_path,
    mock_valid_token,
):
    """Test the successful upload of a batch of samples."""
    resolved_path = (
        Path(__file__).parent / "data/reads/tuberculosis_1_1.fastq.gz"
    )  # not cleanest solution but should work for path resolution
    batch = UploadBatch(
        samples=[
            UploadSample(
                sample_name="sample1",
                instrument_platform="illumina",
                collection_date="2023-10-01",
                country="GBR",
                upload_csv="batch1.csv",
                reads_1="tests/data/reads/tuberculosis_1_1.fastq.gz",
                reads_1_resolved_path=resolved_path,
                control="positive",
            )
        ]
    )
    mock_create_batch_on_server.return_value = (
        "batch_id",
        "local_batch_name",
        "remote_batch_name",
        "legacy_batch_id",
    )
    mock_prepare_files.return_value = {
        "uploadSession": "session_id",
        "uploadSessionData": {"name": "session_name"},
        "files": [
            {
                "file": {
                    "name": "file1",
                    "resolved_path": resolved_path,
                },
                "sample_id": "remote_sample1",
            }
        ],
    }

    upload_batch(batch=batch, save=True, host="mock_host", validate_only=False)

    mock_create_batch_on_server.assert_called_once()
    mock_prepare_files.assert_called_once()
    mock_write_csv.assert_called_once()
    mock_upload_fastq.assert_called_once()


@patch("gpas.lib.get_access_token", return_value="mock_valid_token")
@patch("gpas.lib.get_token_path", return_value=Path("/mock/path/to/token.json"))
@patch("pathlib.Path.read_text", return_value='{"access_token": "mock_valid_token"}')
@patch("gpas.lib.create_batch_on_server")
@patch("gpas.lib.prepare_files")
@patch("gpas.lib.upload_utils.upload_fastq")
@patch("gpas.lib.util.write_csv")
def test_upload_batch_success_validate_only(
    mock_write_csv,
    mock_upload_fastq,
    mock_prepare_files,
    mock_create_batch_on_server,
    mock_read_text,
    mock_token_path,
    mock_valid_token,
):
    """Test the uploading samples with the validate_only flag just validates the batch and doesn't actually upload."""
    batch = UploadBatch(
        samples=[
            UploadSample(
                sample_name="sample1",
                instrument_platform="illumina",
                collection_date="2023-10-01",
                country="GBR",
                upload_csv="batch1.csv",
                reads_1="tests/data/reads/tuberculosis_1_1.fastq.gz",
                control="positive",
            )
        ]
    )
    mock_create_batch_on_server.return_value = (
        "batch_id",
        "local_batch_name",
        "remote_batch_name",
        "legacy_batch_id",
    )
    mock_prepare_files.return_value = {
        "uploadSession": "session_id",
        "uploadSessionData": {"name": "session_name"},
        "files": [{"file": {"name": "file1"}, "sample_id": "sample1"}],
    }

    upload_batch(batch=batch, save=True, host="mock_host", validate_only=True)

    mock_create_batch_on_server.assert_called_once_with(
        batch=batch, host="mock_host", amplicon_scheme=None, validate_only=True
    )
    mock_prepare_files.assert_not_called()
    mock_write_csv.assert_not_called()
    mock_upload_fastq.assert_not_called()


@patch("gpas.lib.get_access_token", return_value="mock_valid_token")
@patch("gpas.lib.get_token_path", return_value=Path("/mock/path/to/token.json"))
@patch("pathlib.Path.read_text", return_value='{"access_token": "mock_valid_token"}')
@patch("gpas.lib.create_batch_on_server")
@patch("gpas.lib.prepare_files")
@patch("gpas.lib.upload_utils.upload_fastq")
@patch("gpas.lib.util.write_csv")
def test_upload_batch_mapping_file(
    mock_write_csv: MagicMock,
    mock_upload_fastq: MagicMock,
    mock_prepare_files: MagicMock,
    mock_create_batch_on_server: MagicMock,
    mock_read_text: MagicMock,
    mock_token_path: MagicMock,
    mock_valid_token: MagicMock,
) -> None:
    """Test the mapping file output constructed in the upload_batch function."""
    resolved_path = (
        Path(__file__).parent / "data/reads/tuberculosis_1_1.fastq.gz"
    )  # not cleanest solution but should work for path resolution
    batch = UploadBatch(
        samples=[
            UploadSample(
                sample_name="sample1",
                instrument_platform="illumina",
                collection_date="2023-10-01",
                country="GBR",
                upload_csv="batch1.csv",
                reads_1="tests/data/reads/tuberculosis_1_1.fastq.gz",
                reads_1_resolved_path=resolved_path,
                control="positive",
            )
        ]
    )
    mock_create_batch_on_server.return_value = (
        "batch_id",
        "local_batch_name",
        "remote_batch_name",
        "legacy_batch_id",
    )

    mock_prepare_files.return_value = {
        "uploadSession": "session_id",
        "uploadSessionData": {"name": "session_name"},
        "files": [
            {
                "file": {
                    "name": "file1",
                    "resolved_path": resolved_path,
                },
                "sample_id": "remote_sample1",
            }
        ],
    }

    upload_batch(batch=batch, save=True, host="mock_host", validate_only=False)

    expected_mapping_records = [
        {
            "batch_name": "local_batch_name",
            "sample_name": "sample1",
            "remote_sample_name": "remote_sample1",
            "remote_batch_name": "remote_batch_name",
            "remote_batch_id": "batch_id",
        }
    ]
    mock_write_csv.assert_called_once_with(
        expected_mapping_records, "remote_batch_name.mapping.csv"
    )
