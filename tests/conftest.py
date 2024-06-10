from pathlib import Path
import pytest

from gpas.create_upload_csv import UploadData
from datetime import datetime


@pytest.fixture
def upload_data():
    return UploadData(
        batch_name="batch_name",
        instrument_platform="illumina",
        collection_date=datetime.strptime("2024-01-01", "%Y-%m-%d"),
        country="GBR",
        host_organism="homo sapiens",
    )


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
def sars_cov_2_1_1_fastq() -> Path:
    return Path("tests/data/reads/sars-cov-2_1_1.fastq")


@pytest.fixture
def sars_cov_2_1_2_fastq() -> Path:
    return Path("tests/data/reads/sars-cov-2_1_2.fastq")


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
