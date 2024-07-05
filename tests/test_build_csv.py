import filecmp
import pytest
import logging

from pydantic import ValidationError
from datetime import datetime

from pathogena.create_upload_csv import build_upload_csv, UploadData


def test_build_csv_illumina(tmp_path, caplog, upload_data):
    caplog.set_level(logging.INFO)
    build_upload_csv(
        "tests/data/empty_files",
        f"{tmp_path}/output.csv",
        upload_data,
    )

    assert filecmp.cmp(
        "tests/data/auto_upload_csvs/illumina.csv", f"{tmp_path}/output.csv"
    )

    assert "Created 1 CSV files: output.csv" in caplog.text
    assert (
        "You can use `pathogena validate` to check the CSV files before uploading."
        in caplog.text
    )


def test_build_csv_ont(tmp_path, caplog, upload_data):
    caplog.set_level(logging.INFO)
    upload_data.instrument_platform = "ont"
    upload_data.district = "dis"
    upload_data.subdivision = "sub"
    upload_data.specimen_organism = "pipe"
    upload_data.host_organism = "unicorn"
    upload_data.ont_read_suffix = "_2.fastq.gz"
    build_upload_csv(
        "tests/data/empty_files",
        f"{tmp_path}/output.csv",
        upload_data,
    )

    assert filecmp.cmp("tests/data/auto_upload_csvs/ont.csv", f"{tmp_path}/output.csv")
    assert "Created 1 CSV files: output.csv" in caplog.text


def test_build_csv_batches(tmp_path, caplog, upload_data):
    caplog.set_level(logging.INFO)
    upload_data.max_batch_size = 3
    build_upload_csv(
        "tests/data/empty_files",
        f"{tmp_path}/output.csv",
        upload_data,
    )

    assert filecmp.cmp(
        "tests/data/auto_upload_csvs/batch1.csv", f"{tmp_path}/output_1.csv"
    )
    assert filecmp.cmp(
        "tests/data/auto_upload_csvs/batch2.csv", f"{tmp_path}/output_2.csv"
    )
    assert "Created 2 CSV files: output_1.csv, output_2.csv" in caplog.text


def test_build_csv_suffix_match(tmp_path, upload_data):
    upload_data.illumina_read2_suffix = "_1.fastq.gz"
    with pytest.raises(ValueError) as e_info:
        build_upload_csv(
            "tests/data/empty_files",
            f"{tmp_path}/output.csv",
            upload_data,
        )
    assert str(e_info.value) == "Must have different reads suffixes"


def test_build_csv_unmatched_files(tmp_path, upload_data):
    with pytest.raises(ValueError) as e_info:
        build_upload_csv(
            "tests/data/unmatched_files",
            f"{tmp_path}/output.csv",
            upload_data,
        )
    assert "Each sample must have two paired files" in str(e_info.value)


def test_build_csv_invalid_tech(tmp_path, upload_data):
    # Note that this should be caught by the model validation
    upload_data.instrument_platform = "invalid"
    with pytest.raises(ValueError) as e_info:
        build_upload_csv(
            "tests/data/unmatched_files",
            f"{tmp_path}/output.csv",
            upload_data,
        )
    assert "Invalid instrument platform" in str(e_info.value)


def test_upload_data_model():
    # Test that making model with invalid country makes error
    with pytest.raises(ValidationError):
        UploadData(
            batch_name="batch_name",
            instrument_platform="invalid",  # type: ignore
            collection_date=datetime.strptime("2024-01-01", "%Y-%m-%d"),
            country="GBR",
        )
    with pytest.raises(ValidationError):
        UploadData(
            batch_name="batch_name",
            instrument_platform="ont",
            collection_date=datetime.strptime("2024-01-01", "%Y-%m-%d"),
            country="G",
        )
    with pytest.raises(ValidationError):
        UploadData(
            batch_name="batch_name",
            instrument_platform="ont",
            collection_date=datetime.strptime("2024-01-01", "%Y-%m-%d"),
            country="GBR",
            specimen_organism="invalid",  # type: ignore
        )
