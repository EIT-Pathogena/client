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
