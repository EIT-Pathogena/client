import logging

from pathlib import Path

import defopt

from gpas_client import lib


def auth():
    username = input("Enter your username: ")
    password = input("Enter your password: ")
    lib.authenticate(username, password)


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
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    lib.upload(upload_csv)


def create_sample(batch_id: int):
    lib.create_sample(batch_id)


def upload_sample_files(sample_id: int, reads_1: Path, reads_2: Path):
    lib.upload_sample_files(sample_id=sample_id, reads_1=reads_1, reads_2=reads_2)


def patch_sample(sample_id: int):
    lib.patch_sample(sample_id)


def sample(sample_id: int):
    lib.sample(sample_id)


def main():
    defopt.run(
        {
            "auth": auth,
            "upload": upload,
            "list": lib.list,
            "create-sample": create_sample,
            "upload-sample": upload_sample_files,
            "patch-sample": patch_sample,
            "sample": lib.fetch_sample,
        },
        no_negated_flags=True,
        strict_kwonly=False,
        short={},
    )
