import os
import subprocess

from pathlib import Path

import pytest

from pydantic import ValidationError

from gpas import lib


def run(cmd: str, cwd: Path = Path()):
    return subprocess.run(
        cmd, cwd=cwd, shell=True, check=True, text=True, capture_output=True
    )


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
