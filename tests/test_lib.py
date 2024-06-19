import logging
import pytest
from gpas import lib


def test_fastq_gz_match(human_1_1_fastq_gz, human_1_2_fastq_gz, caplog):
    logging.getLogger().setLevel(
        logging.INFO
    )  # This is the default level when calling from the CLI
    assert lib.valid_fastq(human_1_1_fastq_gz, human_1_2_fastq_gz)
    assert "Checking FASTQ files" in caplog.text


def test_not_fastq_gz_match(bad_1_1_fastq_gz, human_1_2_fastq_gz, caplog):
    assert not lib.valid_fastq(bad_1_1_fastq_gz, human_1_2_fastq_gz)
    assert (
        "FASTQ file tests/data/reads/bad_1_1.fastq.gz does not have a multiple of 4 lines"
        in caplog.text
    )
    assert (
        "FASTQ files tests/data/reads/bad_1_1.fastq.gz (5 lines) and tests/data/reads/human_1_2.fastq.gz (4 lines) do not have the same number of lines"
        in caplog.text
    )
    pass


def test_fastq_match(sars_cov_2_1_1_fastq, sars_cov_2_1_2_fastq):
    assert lib.valid_fastq(sars_cov_2_1_1_fastq, sars_cov_2_1_2_fastq)


def test_fastq_empty_ont(empty_fastq_1, caplog):
    assert not lib.valid_fastq(empty_fastq_1)
    assert "FASTQ file tests/data/empty_files/read_1_1.fastq is empty" in caplog.text


def test_fastq_gz_empty_ont(empty_fastq_gz_1):
    assert not lib.valid_fastq(empty_fastq_gz_1)


def test_fastq_empty_illumina(empty_fastq_1, empty_fastq_2):
    assert not lib.valid_fastq(empty_fastq_1, empty_fastq_2)


def test_fastq_gz_empty_illumina(empty_fastq_gz_1, empty_fastq_gz_2):
    assert not lib.valid_fastq(empty_fastq_gz_1, empty_fastq_gz_2)


def test_validate_fastqs_illumina(illumina_2_samples_batch, illumina_2_samples_csv):
    lib.validate_fastqs(illumina_2_samples_batch, illumina_2_samples_csv)


def test_mismatched_fastqs_illumina(illumina_2_mismatch_batch, illumina_2_mismatch_csv):
    with pytest.raises(RuntimeError) as excinfo:
        lib.validate_fastqs(illumina_2_mismatch_batch, illumina_2_mismatch_csv)
        assert "FASTQ files are not valid" in str(excinfo.value)


def test_validate_fastqs_ont(ont_2_samples_batch, ont_2_samples_csv):
    lib.validate_fastqs(ont_2_samples_batch, ont_2_samples_csv)
