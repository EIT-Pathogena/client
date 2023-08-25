import os
import subprocess

from pathlib import Path

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
