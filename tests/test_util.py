from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from gpas import util
from gpas.upload_utils import SampleFileMetadata, prepare_file


def test_reads_lines_from_gzip() -> None:
    """Test that the `reads_lines_from_gzip` function correctly reads the expected number of lines from a gzip file."""
    expected_lines = 4
    file_path = Path(__file__).parent / "data" / "reads" / "tuberculosis_1_1.fastq.gz"
    lines = util.reads_lines_from_gzip(file_path=file_path)
    assert lines == expected_lines


def test_reads_lines_from_fastq() -> None:
    """Test that the `reads_lines_from_fastq` function correctly reads the expected number of lines from a fastq file."""
    expected_lines = 4
    file_path = Path(__file__).parent / "data" / "reads" / "tuberculosis_1_1.fastq"
    lines = util.reads_lines_from_fastq(file_path=file_path)
    assert lines == expected_lines


def test_fail_command_exists() -> None:
    """Test that the `command_exists` function correctly identifies a non-existent command."""
    assert not util.command_exists("notarealcommandtest")


def test_find_duplicate_entries() -> None:
    """Test that the `find_duplicate_entries` function correctly identifies duplicate entries in a list."""
    data = ["foo", "foo", "bar", "bar", "baz"]
    expected = ["foo", "bar"]
    duplicates = util.find_duplicate_entries(data)
    assert duplicates == expected


def test_find_no_duplicate_entries() -> None:
    """Test that the `find_duplicate_entries` function correctly identifies that there are no duplicate entries in a list."""
    data = ["foo", "bar"]
    expected = []
    duplicates = util.find_duplicate_entries(data)
    assert duplicates == expected


def test_prepare_file_success():
    resolved_path = Path("/mock/path/to/file.fastq.gz")
    file_metadata = {
        "name": "file.fastq.gz",
        "size": 1024,
        "content_type": "application/gzip",
        "specimen_organism": "MockOrganism",
        "resolved_path": resolved_path,
        "control": "MockControl",
    }
    batch_pk = "123"
    upload_session = 456
    sample_id = "sample123"
    api_client = MagicMock()

    api_client.batches_uploads_start_file_upload.return_value.json.return_value = {
        "upload_id": 789,
        "sample_id": sample_id,
        "sample_file_id": 101112,
    }
    api_client.batches_uploads_start_file_upload.return_value.status_code = 200

    mock_file_data = b"mock_file_data"
    with patch("pathlib.Path.open", mock_open(read_data=mock_file_data)):
        result = prepare_file(
            resolved_path=resolved_path,
            file_metadata=file_metadata,
            batch_pk=batch_pk,
            upload_session=upload_session,
            sample_id=sample_id,
            api_client=api_client,
        )

    assert result["file"] == file_metadata
    assert result["upload_id"] == 789
    assert result["batch_id"] == batch_pk
    assert result["sample_id"] == sample_id
    assert result["sample_file_id"] == 101112
    assert result["total_chunks"] > 0
    assert result["upload_session"] == upload_session
    assert result["file_data"] == mock_file_data


def test_prepare_file_missing_path():
    resolved_path = None
    file_metadata = {
        "name": "file.fastq.gz",
        "size": 1024,
        "content_type": "application/gzip",
        "specimen_organism": "MockOrganism",
        "resolved_path": resolved_path,
        "control": "MockControl",
    }
    batch_pk = "123"
    upload_session = 456
    sample_id = "sample123"
    api_client = MagicMock()

    result = prepare_file(
        resolved_path=resolved_path,
        file_metadata=file_metadata,
        batch_pk=batch_pk,
        upload_session=upload_session,
        sample_id=sample_id,
        api_client=api_client,
    )

    assert result["error"] == "Could not find any read file data for sample"
    assert result["status code"] == 500
    assert result["upload_session"] == upload_session
