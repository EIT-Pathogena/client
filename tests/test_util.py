from pathlib import Path
from gpas import util


def test_reads_lines_from_gzip():
    expected_lines = 4
    file_path = Path(__file__).parent / "data" / "reads" / "tuberculosis_1_1.fastq.gz"
    lines = util.reads_lines_from_gzip(file_path=file_path)
    assert lines == expected_lines


def test_reads_lines_from_fastq():
    expected_lines = 4
    file_path = Path(__file__).parent / "data" / "reads" / "tuberculosis_1_1.fastq"
    lines = util.reads_lines_from_fastq(file_path=file_path)
    assert lines == expected_lines


def test_fail_command_exists():
    assert not util.command_exists("notarealcommandtest")


def test_command_exists():
    assert util.command_exists("python")
