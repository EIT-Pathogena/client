from click.testing import CliRunner
from gpas import __version__ as version
from gpas.cli import main


def test_cli_help_override():
    runner = CliRunner()
    result = runner.invoke(main, ["upload", "-h"])
    assert result.exit_code == 0


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert version in result.output


def test_cli_decontaminate_ont(ont_sample_csv):
    runner = CliRunner()
    result = runner.invoke(main, ["decontaminate", str(ont_sample_csv)])
    assert result.exit_code == 0


def test_cli_decontaminate_illumina(illumina_sample_csv):
    runner = CliRunner()
    result = runner.invoke(main, ["decontaminate", str(illumina_sample_csv)])
    assert result.exit_code == 0


def test_cli_upload_ont(ont_sample_csv):
    runner = CliRunner()
    result = runner.invoke(main, ["upload", str(ont_sample_csv)])
    assert result.exit_code == 0


def test_cli_upload_illumina(illumina_sample_csv):
    runner = CliRunner()
    result = runner.invoke(main, ["upload", str(illumina_sample_csv)])
    assert result.exit_code == 0


def test_cli_upload_skip_decontamination_ont(ont_sample_csv):
    runner = CliRunner()
    result = runner.invoke(
        main, ["upload", str(ont_sample_csv), "--skip-decontamination"]
    )
    assert result.exit_code == 0


def test_cli_upload_skip_decontamination_illumina(illumina_sample_csv):
    runner = CliRunner()
    result = runner.invoke(
        main, ["upload", str(illumina_sample_csv), "--skip-decontamination"]
    )
    assert result.exit_code == 0


def test_cli_upload_skip_fastq_checks(ont_sample_csv):
    runner = CliRunner()
    result = runner.invoke(main, ["upload", str(ont_sample_csv), "--skip-fastq-check"])
    assert result.exit_code == 0
