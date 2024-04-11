import os

import pytest
import filecmp

from pydantic import ValidationError

from gpas import lib, models
from gpas.util import run
from gpas.create_upload_csv import build_upload_csv


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


def test_build_csv_illumina(tmp_path):
    build_upload_csv(
        "tests/data/empty_files",
        f"{tmp_path}/output.csv",
        "illumina",
        "batch_name",
        "2024-01-01",
        "GBR",
    )

    assert filecmp.cmp(
        "tests/data/auto_upload_csvs/illumina.csv", f"{tmp_path}/output.csv"
    )


def test_build_csv_ont(tmp_path):
    build_upload_csv(
        "tests/data/empty_files",
        f"{tmp_path}/output.csv",
        "ont",
        "batch_name",
        "2024-01-01",
        "GBR",
        district="dis",
        subdivision="sub",
        pipeline="pipe",
        host_organism="unicorn",
        ont_read_suffix="_2.fastq.gz",
    )

    assert filecmp.cmp("tests/data/auto_upload_csvs/ont.csv", f"{tmp_path}/output.csv")


def test_build_csv_batches(tmp_path):
    build_upload_csv(
        "tests/data/empty_files",
        f"{tmp_path}/output.csv",
        "illumina",
        "batch_name",
        "2024-01-01",
        "GBR",
        max_batch_size=3,
    )

    assert filecmp.cmp(
        "tests/data/auto_upload_csvs/batch1.csv", f"{tmp_path}/output_1.csv"
    )
    assert filecmp.cmp(
        "tests/data/auto_upload_csvs/batch2.csv", f"{tmp_path}/output_2.csv"
    )
