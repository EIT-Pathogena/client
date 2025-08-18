from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from pathogena.create_upload_csv import UploadData
from pathogena.models import UploadBatch, UploadSample, create_batch_from_csv


@pytest.fixture(scope="session", autouse=True)
def mock_amplicon_scheme():
    with patch("pathogena.lib.get_amplicon_schemes") as get_amplicon_schemes_mock:
        get_amplicon_schemes_mock.return_value = []
        yield


@pytest.fixture
def cli_main():
    # Required to be a fixture to ensure it is patched before use
    from pathogena.cli import main

    return main


@pytest.fixture
def upload_data() -> UploadData:
    return UploadData(
        batch_name="batch_name",
        instrument_platform="illumina",
        collection_date=datetime.strptime("2024-01-01", "%Y-%m-%d"),
        country="GBR",
        host_organism="homo sapiens",
    )


@pytest.fixture
def upload_data_sars_cov_2_amp() -> UploadData:
    return UploadData(
        batch_name="batch_name",
        instrument_platform="illumina",
        collection_date=datetime.strptime("2024-01-01", "%Y-%m-%d"),
        country="GBR",
        host_organism="homo sapiens",
        specimen_organism="sars-cov-2",
        amplicon_scheme="COVID-AMPLISEQ-V1",
    )


@pytest.fixture
def test_host() -> str:
    return "portal.eit-pathogena.com"


@pytest.fixture
def reads() -> Path:
    return Path("tests/data/reads")


@pytest.fixture
def human_1_1_fastq_gz() -> Path:
    return Path("tests/data/reads/human_1_1.fastq.gz")


@pytest.fixture
def human_1_2_fastq_gz() -> Path:
    return Path("tests/data/reads/human_1_2.fastq.gz")


@pytest.fixture
def bad_1_1_fastq_gz() -> Path:
    return Path("tests/data/reads/bad_1_1.fastq.gz")


@pytest.fixture
def sars_cov_2_1_1_fastq_gz() -> Path:
    return Path("tests/data/reads/sars-cov-2_1_1.fastq.gz")


@pytest.fixture
def sars_cov_2_1_2_fastq_gz() -> Path:
    return Path("tests/data/reads/sars-cov-2_1_2.fastq.gz")


@pytest.fixture
def empty_fastq_1() -> Path:
    return Path("tests/data/empty_files/read_1_1.fastq")


@pytest.fixture
def empty_fastq_2() -> Path:
    return Path("tests/data/empty_files/read_1_2.fastq")


@pytest.fixture
def empty_fastq_gz_1() -> Path:
    return Path("tests/data/empty_files/read_1_1.fastq.gz")


@pytest.fixture
def empty_fastq_gz_2() -> Path:
    return Path("tests/data/empty_files/read_1_2.fastq.gz")


@pytest.fixture
def invalid_fastq_paths_csv() -> Path:
    return Path("tests/data/invalid/invalid-fastq-path.csv")


@pytest.fixture
def illumina_sample_csv() -> Path:
    return Path("tests/data/illumina.csv")


@pytest.fixture
def illumina_gzipped_sample_csv() -> Path:
    return Path("tests/data/illumina-gzipped.csv")


@pytest.fixture
def illumina_multiple_sample_csv() -> Path:
    return Path("tests/data/illumina-2.csv")


@pytest.fixture
def illumina_mismatched_fastqs_csv() -> Path:
    return Path("tests/data/invalid/mismatched-fastqs.csv")


@pytest.fixture
def ont_sample_csv() -> Path:
    return Path("tests/data/ont.csv")


@pytest.fixture
def ont_gzipped_sample_csv() -> Path:
    return Path("tests/data/ont-gzipped.csv")


@pytest.fixture
def illumina_sars_cov_2_gzipped_sample_csv() -> Path:
    return Path("tests/data/sars-cov-2_illumina.csv")


@pytest.fixture
def illumina_sars_cov_2_amp_gzipped_sample_csv() -> Path:
    return Path("tests/data/sars_cov_2_illumina_amp_scheme.csv")


@pytest.fixture
def illumina_sars_cov_2_bad_amp_gzipped_sample_csv() -> Path:
    return Path("tests/data/sars_cov_2_illumina_bad_amp_scheme.csv")


@pytest.fixture
def illumina_sars_cov_2_mix_amp_gzipped_sample_csv() -> Path:
    return Path("tests/data/sars_cov_2_illumina_mix_amp_scheme.csv")


@pytest.fixture
def myco_illumina_amp() -> Path:
    return Path("tests/data/myco_illumina_amp.csv")


@pytest.fixture
def ont_multiple_sample_csv() -> Path:
    return Path("tests/data/ont-2.csv")


@pytest.fixture
def empty_sample_name_csv() -> Path:
    return Path("tests/data/invalid/empty-sample-name.csv")


@pytest.fixture
def empty_fastq_csv() -> Path:
    return Path("tests/data/invalid/empty-fastq.csv")


@pytest.fixture
def invalid_control_csv() -> Path:
    return Path("tests/data/invalid/invalid-control.csv")


@pytest.fixture
def invalid_specimen_organism_csv() -> Path:
    return Path("tests/data/invalid/invalid-specimen-organism.csv")


@pytest.fixture
def invalid_mixed_platform_csv() -> Path:
    return Path("tests/data/invalid/mixed-instrument-platform.csv")


@pytest.fixture
def invalid_instrument_platform_csv() -> Path:
    return Path("tests/data/invalid/invalid-instrument-platform.csv")


@pytest.fixture
def empty_specimen_organism_csv() -> Path:
    return Path("tests/data/invalid/empty-specimen-organism.csv")


# Batches
@pytest.fixture
def ont_sample_batch(ont_sample_csv: Path) -> UploadBatch:
    return create_batch_from_csv(ont_sample_csv)


@pytest.fixture
def ont_multiple_sample_batch(ont_multiple_sample_csv: Path) -> UploadBatch:
    return create_batch_from_csv(ont_multiple_sample_csv)


@pytest.fixture
def illumina_sample_batch(illumina_sample_csv: Path) -> UploadBatch:
    return create_batch_from_csv(illumina_sample_csv)


@pytest.fixture
def illumina_multiple_sample_batch(illumina_multiple_sample_csv: Path) -> UploadBatch:
    return create_batch_from_csv(illumina_multiple_sample_csv)


@pytest.fixture
def invalid_fastq_paths_batch(invalid_fastq_paths_csv: Path) -> Path:
    return create_batch_from_csv(invalid_fastq_paths_csv)


@pytest.fixture
def illumina_2_mismatch_batch(illumina_mismatched_fastqs_csv: Path) -> UploadBatch:
    return create_batch_from_csv(illumina_mismatched_fastqs_csv)


# Samples
@pytest.fixture
def ont_sample(ont_sample_batch) -> UploadSample:
    return ont_sample_batch.samples[0]


@pytest.fixture
def illumina_sample(illumina_sample_batch) -> UploadSample:
    return illumina_sample_batch.samples[0]
