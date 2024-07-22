import os

from click.testing import CliRunner
from pydantic import ValidationError

from pathogena import __version__ as version
from pathogena.cli import main


def test_cli_help_override():
    runner = CliRunner()
    result = runner.invoke(main, ["upload", "-h"])
    assert result.exit_code == 0


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert version in result.output


# Github Action currently exits 143 with this test, likely what the previous comment meant by "Slow"
# def test_cli_decontaminate_ont(ont_sample_csv):
#     runner = CliRunner()
#     result = runner.invoke(main, ["decontaminate", str(ont_sample_csv)])
#     assert result.exit_code == 0
#     [os.remove(f) for f in os.listdir(".") if f.endswith("clean.fastq.gz")]


def test_cli_decontaminate_illumina(illumina_sample_csv):
    runner = CliRunner()
    result = runner.invoke(main, ["decontaminate", str(illumina_sample_csv)])
    assert result.exit_code == 0
    [os.remove(f) for f in os.listdir(".") if f.endswith(".fastq.gz")]


def test_cli_decontaminate_illumina_with_output_dir(illumina_sample_csv):
    runner = CliRunner()
    result = runner.invoke(
        main, ["decontaminate", str(illumina_sample_csv), "--output-dir", "."]
    )
    assert result.exit_code == 0
    [os.remove(f) for f in os.listdir(".") if f.endswith(".fastq.gz")]


def test_cli_fail_decontaminate_output_dir(illumina_sample_csv):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["decontaminate", str(illumina_sample_csv), "--output-dir", "totallyfakedir"],
    )
    assert result.exit_code != 0
    assert "Directory 'totallyfakedir' does not exist" in result.stdout


def test_cli_fail_upload_output_dir(illumina_sample_csv):
    runner = CliRunner()
    result = runner.invoke(
        main, ["upload", str(illumina_sample_csv), "--output-dir", "totallyfakedir"]
    )
    assert result.exit_code != 0
    assert "Directory 'totallyfakedir' does not exist" in result.stdout


def test_cli_fail_download_output_dir(illumina_sample_csv):
    runner = CliRunner()
    result = runner.invoke(main, ["download", "--output-dir", "totallyfakedir"])
    assert result.exit_code != 0
    assert "Directory 'totallyfakedir' does not exist" in result.stdout


def test_validation_fail_control(invalid_control_csv):
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(invalid_control_csv)])
    assert result.exit_code == 1
    assert result.exc_info[0] == ValidationError
    assert "Input should be 'positive', 'negative' or ''" in str(result.exc_info)


# Doesn't work because it actually uploads data, need to work out a mock system or break down the function
# even further, for now, an authenticated used can un-comment and run the tests.
# TODO: Re-implement with a mock upload somehow.
# def test_validation(illumina_sample_csv):
#     runner = CliRunner()
#     result = runner.invoke(main, ["validate", str(illumina_sample_csv)])
#     assert result.exit_code == 0
#
#
# def test_cli_upload_ont(ont_sample_csv):
#     runner = CliRunner()
#     result = runner.invoke(main, ["upload", str(ont_sample_csv)])
#     assert result.exit_code == 0
#
#
# def test_cli_upload_illumina(illumina_sample_csv):
#     runner = CliRunner()
#     result = runner.invoke(main, ["upload", str(illumina_sample_csv)])
#     assert result.exit_code == 0
#
#
# def test_cli_upload_skip_decontamination_ont(ont_sample_csv):
#     runner = CliRunner()
#     result = runner.invoke(
#         main, ["upload", str(ont_sample_csv), "--skip-decontamination"]
#     )
#     assert result.exit_code == 0
#
#
# def test_cli_upload_skip_decontamination_illumina(illumina_sample_csv):
#     runner = CliRunner()
#     result = runner.invoke(
#         main, ["upload", str(illumina_sample_csv), "--skip-decontamination"]
#     )
#     assert result.exit_code == 0
#
#
# def test_cli_upload_skip_fastq_checks(ont_sample_csv):
#     runner = CliRunner()
#     result = runner.invoke(main, ["upload", str(ont_sample_csv), "--skip-fastq-check"])
#     assert result.exit_code == 0
