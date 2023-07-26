from pathlib import Path

import defopt

from gpas_client import lib


def auth():
    pass


def upload(
    upload_csv: Path,
    out_dir: Path = Path(),
    threads: int = 0,
    debug: bool = False,
    save_reads: bool = False,
):
    """
    Validate, decontaminate and upload reads to the GPAS platform

    :arg upload_csv: Path of upload csv
    :arg out_dir: Path of directory in which to save mapping CSV
    :arg save_reads: Save decontaminated reads in out_dir
    :arg threads: Number of threads used in decontamination
    :arg debug: Emit verbose debug messages
    """
    lib.upload(upload_csv)


def main():
    defopt.run(
        {"auth": auth, "upload": upload},
        no_negated_flags=True,
        strict_kwonly=False,
        short={},
    )
