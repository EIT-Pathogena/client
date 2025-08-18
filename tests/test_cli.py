import os
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from pathogena import __version__ as version


def test_cli_help_override(cli_main) -> None:
    """Test the CLI help command.

    This test ensures that the help message for the 'upload' command is displayed correctly.
    """
    runner = CliRunner()
    result = runner.invoke(cli_main, ["upload", "-h"])
    assert result.exit_code == 0


def test_cli_version(cli_main) -> None:
    """Test the CLI version command.

    This test ensures that the version of the CLI is displayed correctly.
    """
    runner = CliRunner()
    result = runner.invoke(cli_main, ["--version"])
    assert result.exit_code == 0
    assert version in result.output


# Github Action currently exits 143 with this test, likely what the previous comment meant by "Slow"
# def test_cli_decontaminate_ont(ont_sample_csv):
#     runner = CliRunner()
#     result = runner.invoke(cli_main, ["decontaminate", str(ont_sample_csv)])
#     assert result.exit_code == 0
#     [os.remove(f) for f in os.listdir(".") if f.endswith("clean.fastq.gz")]


@pytest.mark.slow
def test_cli_decontaminate_illumina(cli_main, illumina_sample_csv: Path) -> None:
    """Test the CLI decontaminate command for Illumina samples.

    Args:
        illumina_sample_csv (Path): Path to the Illumina sample CSV file.
    """
    runner = CliRunner()
    result = runner.invoke(cli_main, ["decontaminate", str(illumina_sample_csv)])
    assert result.exit_code == 0
    [os.remove(f) for f in os.listdir(".") if f.endswith(".fastq.gz")]


@pytest.mark.slow
def test_cli_decontaminate_illumina_with_output_dir(
    cli_main, illumina_sample_csv: Path
) -> None:
    """Test the CLI decontaminate command for Illumina samples with an output directory.

    Args:
        illumina_sample_csv (Path): Path to the Illumina sample CSV file.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli_main, ["decontaminate", str(illumina_sample_csv), "--output-dir", "."]
    )
    assert result.exit_code == 0
    [os.remove(f) for f in os.listdir(".") if f.endswith(".fastq.gz")]


@pytest.mark.slow
def test_cli_fail_decontaminate_output_dir(cli_main, illumina_sample_csv: Path) -> None:
    """Test the CLI decontaminate command failure with a non-existent output directory.

    Args:
        illumina_sample_csv (Path): Path to the Illumina sample CSV file.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        ["decontaminate", str(illumina_sample_csv), "--output-dir", "totallyfakedir"],
    )
    assert result.exit_code != 0
    assert (
        "Directory 'totallyfakedir' does not exist" in result.stdout
        or "Directory 'totallyfakedir' does not exist" in result.stderr
    )


def test_cli_fail_upload_output_dir(cli_main, illumina_sample_csv: Path) -> None:
    """Test the CLI upload command failure with a non-existent output directory.

    Args:
        illumina_sample_csv (Path): Path to the Illumina sample CSV file.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli_main, ["upload", str(illumina_sample_csv), "--output-dir", "totallyfakedir"]
    )
    assert result.exit_code != 0
    assert (
        "Directory 'totallyfakedir' does not exist" in result.stdout
        or "Directory 'totallyfakedir' does not exist" in result.stderr
    )


def test_cli_fail_download_output_dir(cli_main, illumina_sample_csv: Path) -> None:
    """Test the CLI download command failure with a non-existent output directory.

    Args:
        illumina_sample_csv (Path): Path to the Illumina sample CSV file.
    """
    runner = CliRunner()
    result = runner.invoke(cli_main, ["download", "--output-dir", "totallyfakedir"])
    assert result.exit_code != 0
    assert (
        "Directory 'totallyfakedir' does not exist" in result.stdout
        or "Directory 'totallyfakedir' does not exist" in result.stderr
    )


def test_validation_fail_control(cli_main, invalid_control_csv: Path) -> None:
    """Test validation failure for control CSV.

    Args:
        invalid_control_csv (Path): Path to the invalid control CSV file.
    """
    runner = CliRunner()
    result = runner.invoke(cli_main, ["validate", str(invalid_control_csv)])
    assert result.exit_code == 1
    assert result.exc_info[0] == ValidationError
    assert "Input should be 'positive', 'negative' or ''" in str(result.exc_info)


def test_build_csv_specimen_organism(cli_main, reads: Path) -> None:
    """Test building a CSV with a specimen organism via the CLI.

    This test is present because the build_csv() function uses a different
    variable name (`pipeline`) for specimen organism.

    Args:
        reads (Path): Path to a reads folder containing `fastq` and `fastq.gz` files.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file_path = Path(temp_dir) / "test_ont.csv"

        runner = CliRunner()
        result = runner.invoke(
            cli_main,
            [
                "build-csv",
                "--output-csv",
                str(temp_file_path),
                "--batch-name",
                "test_ont",
                "--country",
                "GBR",
                "--instrument-platform",
                "ont",
                str(reads),
            ],
        )
        assert result.exit_code == 0


# Doesn't work because it actually uploads data, need to work out a mock system or break down the function
# even further, for now, an authenticated used can un-comment and run the tests.
# TODO: Re-implement with a mock upload somehow.  # noqa: TD002, TD003
# def test_validation(illumina_sample_csv):
#     runner = CliRunner()
#     result = runner.invoke(cli_main, ["validate", str(illumina_sample_csv)])
#     assert result.exit_code == 0
#
#
# def test_cli_upload_ont(ont_sample_csv):
#     runner = CliRunner()
#     result = runner.invoke(cli_main, ["upload", str(ont_sample_csv)])
#     assert result.exit_code == 0
#
#
# def test_cli_upload_illumina(illumina_sample_csv):
#     runner = CliRunner()
#     result = runner.invoke(cli_main, ["upload", str(illumina_sample_csv)])
#     assert result.exit_code == 0
#
#
# def test_cli_upload_skip_decontamination_ont(ont_sample_csv):
#     runner = CliRunner()
#     result = runner.invoke(
#         cli_main, ["upload", str(ont_sample_csv), "--skip-decontamination"]
#     )
#     assert result.exit_code == 0
#
#
# def test_cli_upload_skip_decontamination_illumina(illumina_sample_csv):
#     runner = CliRunner()
#     result = runner.invoke(
#         cli_main, ["upload", str(illumina_sample_csv), "--skip-decontamination"]
#     )
#     assert result.exit_code == 0
#
#
# def test_cli_upload_skip_fastq_checks(ont_sample_csv):
#     runner = CliRunner()
#     result = runner.invoke(cli_main, ["upload", str(ont_sample_csv), "--skip-fastq-check"])
#     assert result.exit_code == 0
