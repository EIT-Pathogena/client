import pytest

from gpas.create_upload_csv import UploadData


@pytest.fixture
def upload_data():
    return UploadData(
        batch_name="batch_name",
        seq_tech="illumina",
        collection_date="2024-01-01",
        country="GBR",
    )
