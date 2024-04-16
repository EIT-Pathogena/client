import os

import filecmp
import pytest
import logging

from pydantic import ValidationError
from datetime import datetime

from gpas import lib, models
from gpas.util import run
from gpas.create_upload_csv import build_upload_csv, UploadData


def test_cli_version():
    run("gpas --version")


def test_illumina_2():
    lib.upload("tests/data/illumina-2.csv", dry_run=True)
    [os.remove(f) for f in os.listdir(".") if f.endswith("fastq.gz")]
    [os.remove(f) for f in os.listdir(".") if f.endswith(".mapping.csv")]


# # Slow
# def test_ont_2():
#     lib.upload("tests/data/ont-2.csv", dry_run=True)
#     [os.remove(f) for f in os.listdir(".") if f.endswith("fastq.gz")]
#     [os.remove(f) for f in os.listdir(".") if f.endswith(".mapping.csv")]


def test_fail_invalid_fastq_path():
    with pytest.raises(ValidationError):
        lib.upload("tests/data/invalid/invalid-fastq-path.csv", dry_run=True)


def test_fail_empty_sample_name():
    with pytest.raises(ValidationError):
        lib.upload("tests/data/invalid/empty-sample-name.csv", dry_run=True)


def test_fail_invalid_control():
    with pytest.raises(ValidationError):
        lib.upload("tests/data/invalid/invalid-control.csv", dry_run=True)


def test_fail_invalid_specimen_organism():
    with pytest.raises(ValidationError):
        lib.upload("tests/data/invalid/invalid-specimen-organism.csv", dry_run=True)


def test_fail_mixed_instrument_platform():
    with pytest.raises(ValidationError):
        lib.upload("tests/data/invalid/mixed-instrument-platform.csv", dry_run=True)


def test_fail_invalid_instrument_platform():
    with pytest.raises(ValidationError):
        lib.upload("tests/data/invalid/invalid-instrument-platform.csv", dry_run=True)


def test_validate_illumina_model():
    models.parse_upload_csv("tests/data/illumina.csv")
    models.parse_upload_csv("tests/data/illumina-2.csv")


def test_validate_ont_model():
    models.parse_upload_csv("tests/data/ont.csv")


def test_validate_fail_invalid_control():
    with pytest.raises(ValidationError):
        lib.validate("tests/data/invalid/invalid-control.csv")


def test_validate_fail_invalid_specimen_organism():
    with pytest.raises(ValidationError):
        lib.validate("tests/data/invalid/invalid-specimen-organism.csv")


def test_validate_fail_mixed_instrument_platform():
    with pytest.raises(ValidationError):
        lib.validate("tests/data/invalid/mixed-instrument-platform.csv")


def test_validate_fail_invalid_instrument_platform():
    with pytest.raises(ValidationError):
        lib.validate("tests/data/invalid/invalid-instrument-platform.csv")


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
        "You can use `gpas validate` to check the CSV files before uploading."
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
