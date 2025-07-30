from pathlib import Path

from gpas import util


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
