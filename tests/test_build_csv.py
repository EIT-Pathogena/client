import filecmp
import logging
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from pathogena.create_upload_csv import UploadData, build_upload_csv


def test_build_csv_illumina(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, upload_data: UploadData
) -> None:
    """Test building CSV for Illumina platform.

    This test checks that the output illumina csv is the same as the temp output csv, that the csv creation
    can be seen in the log output, and that some help text can be seen in the log output.

    Args:
        tmp_path (Path): Temporary path for output files.
        caplog (pytest.LogCaptureFixture): Fixture to capture log output.
        upload_data (UploadData): Data required for building the upload CSV.
    """
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


def test_build_csv_illumina_sars_cov_2_amp(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    upload_data_sars_cov_2_amp: UploadData,
) -> None:
    """Test building CSV for Illumina platform.

    This test checks that the output illumina csv is the same as the temp output csv, that the csv creation
    can be seen in the log output, and that some help text can be seen in the log output.

    Args:
        tmp_path (Path): Temporary path for output files.
        caplog (pytest.LogCaptureFixture): Fixture to capture log output.
        upload_data_sars_cov_2_amp (UploadData): Data required for building the upload CSV.
    """
    caplog.set_level(logging.INFO)
    build_upload_csv(
        "tests/data/empty_files",
        f"{tmp_path}/output.csv",
        upload_data_sars_cov_2_amp,
    )

    assert filecmp.cmp(
        "tests/data/auto_upload_csvs/sars_cov_2_illumina_amp_scheme.csv",
        f"{tmp_path}/output.csv",
    )

    assert "Created 1 CSV files: output.csv" in caplog.text
    assert (
        "You can use `pathogena validate` to check the CSV files before uploading."
        in caplog.text
    )


def test_build_csv_ont(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, upload_data: UploadData
) -> None:
    """Test building CSV for ONT platform.

    This test checks that the output ont csv is the same as the temp output csv, and that the csv creation
    can be seen in the log output.

    Args:
        tmp_path (Path): Temporary path for output files.
        caplog (pytest.LogCaptureFixture): Fixture to capture log output.
        upload_data (UploadData): Data required for building the upload CSV.
    """
    caplog.set_level(logging.INFO)
    upload_data.instrument_platform = "ont"
    upload_data.district = "dis"
    upload_data.subdivision = "sub"
    upload_data.specimen_organism = "mycobacteria"
    upload_data.host_organism = "unicorn"
    upload_data.ont_read_suffix = "_2.fastq.gz"
    build_upload_csv(
        "tests/data/empty_files",
        f"{tmp_path}/output.csv",
        upload_data,
    )

    assert filecmp.cmp("tests/data/auto_upload_csvs/ont.csv", f"{tmp_path}/output.csv")
    assert "Created 1 CSV files: output.csv" in caplog.text


def test_build_csv_batches(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, upload_data: UploadData
) -> None:
    """Test building CSV in batches.

    This test checks that the both of the batch csvs are the same as the temp output csvs, and that the csv creation
    can be seen in the log output.

    Args:
        tmp_path (Path): Temporary path for output files.
        caplog (pytest.LogCaptureFixture): Fixture to capture log output.
        upload_data (UploadData): Data required for building the upload CSV.
    """
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


def test_build_csv_suffix_match(tmp_path: Path, upload_data: UploadData) -> None:
    """Test building CSV with matching read suffixes.

    This test checks that an empty samples folder raises an error, and that the corresponding error message is
    as expected.

    Args:
        tmp_path (Path): Temporary path for output files.
        upload_data (UploadData): Data required for building the upload CSV.
    """
    upload_data.illumina_read2_suffix = "_1.fastq.gz"
    with pytest.raises(ValueError) as e_info:
        build_upload_csv(
            "tests/data/empty_files",
            f"{tmp_path}/output.csv",
            upload_data,
        )
    assert str(e_info.value) == "Must have different reads suffixes"


def test_build_csv_unmatched_files(tmp_path: Path, upload_data: UploadData) -> None:
    """Test building CSV with unmatched files.

    This test checks that a samples folder with unmatched files raises an error, and that the corresponding
    error message is as expected.

    Args:
        tmp_path (Path): Temporary path for output files.
        upload_data (UploadData): Data required for building the upload CSV.
    """
    with pytest.raises(ValueError) as e_info:
        build_upload_csv(
            "tests/data/unmatched_files",
            f"{tmp_path}/output.csv",
            upload_data,
        )
    assert "Each sample must have two paired files" in str(e_info.value)


def test_build_csv_invalid_tech(tmp_path: Path, upload_data: UploadData) -> None:
    """Test building CSV with an invalid instrument platform.

    This test checks that an invalid instrument platform together with a samples folder with unmatched files
    raises an error, and that the corresponding error message is as expected.

    Note that this should be caught by the model validation.

    Args:
        tmp_path (Path): Temporary path for output files.
        upload_data (UploadData): Data required for building the upload CSV.
    """
    upload_data.instrument_platform = "invalid"
    with pytest.raises(ValueError) as e_info:
        build_upload_csv(
            "tests/data/unmatched_files",
            f"{tmp_path}/output.csv",
            upload_data,
        )
    assert "Invalid instrument platform" in str(e_info.value)


def test_build_csv_invalid_specimen_organism(
    tmp_path: Path, upload_data: UploadData
) -> None:
    """Test building CSV with an invalid specimen organism.

    This test checks that an invalid specimen organism
    raises an error, and that the corresponding error message is as expected.

    Note that this should be caught by the model validation.

    Args:
        tmp_path (Path): Temporary path for output files.
        upload_data (UploadData): Data required for building the upload CSV.
    """
    upload_data.specimen_organism = "invalid"
    with pytest.raises(ValueError) as e_info:
        build_upload_csv(
            "tests/data/empty_files",
            f"{tmp_path}/output.csv",
            upload_data,
        )
    assert "Invalid pipeline" in str(e_info.value)


def test_upload_data_model() -> None:
    """Test the UploadData model validation.

    This test ensures that the UploadData model raises validation errors for invalid data, such as platform, country and
    specimen_organism.
    """
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
