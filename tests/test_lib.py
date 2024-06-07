import pytest
from gpas import lib


def test_fastq_match(human_1_1_fastq_gz, human_1_2_fastq_gz):
    assert lib.fastq_match(human_1_1_fastq_gz, human_1_2_fastq_gz)


def test_not_fastq_match(bad_1_1_fastq_gz, human_1_2_fastq_gz):
    assert not lib.fastq_match(bad_1_1_fastq_gz, human_1_2_fastq_gz)
