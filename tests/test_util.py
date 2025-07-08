from pathlib import Path

from pathogena import util


def test_reads_lines_from_gzip() -> None:
    """Test that the `reads_lines_from_gzip` function correctly reads the expected number of lines from a gzip file."""
    file_path = Path(__file__).parent / "data" / "reads" / "tuberculosis_1_1.fastq.gz"
    num_lines = util.count_lines_in_gzip(file_path=file_path)
    assert num_lines == 4


def test_reads_lines_from_fastq() -> None:
    """Test that the `reads_lines_from_fastq` function correctly reads the expected number of lines from a fastq file."""
    file_path = Path(__file__).parent / "data" / "reads" / "tuberculosis_1_1.fastq"
    num_lines = util.reads_lines_from_fastq(file_path=file_path)
    assert num_lines == 4


def test_fail_command_exists() -> None:
    """Test that the `command_exists` function correctly identifies a non-existent command."""
    assert not util.command_exists("notarealcommandtest")


def test_find_duplicate_entries() -> None:
    """Test that the `find_duplicate_entries` function correctly identifies duplicate entries in a list."""
    data = ["foo", "foo", "bar", "bar", "baz"]
    duplicates = util.find_duplicate_entries(data)
    assert duplicates == ["foo", "bar"]


def test_find_no_duplicate_entries() -> None:
    """Test that the `find_duplicate_entries` function correctly identifies that there are no duplicate entries in a list."""
    data = ["foo", "bar"]
    duplicates = util.find_duplicate_entries(data)
    assert duplicates == []
