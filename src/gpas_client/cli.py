import json
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
    save_reads: bool = False,
    dry_run: bool = False,
    debug: bool = False,
):
    """
    Validate, decontaminate and upload reads to the GPAS platform

    :arg upload_csv: Path of upload csv
    :arg out_dir: Path of directory in which to save mapping CSV
    :arg save_reads: Save decontaminated reads in out_dir
    :arg threads: Number of threads used in decontamination
    :arg debug: Emit verbose debug messages
    :arg dry_run: Exit before uploading reads
    """
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    lib.upload(upload_csv, dry_run=dry_run)


def batches():
    """List batches on server"""
    print(json.dumps(lib.list_batches()))


def samples():
    """List samples on server"""
    print(json.dumps(lib.list_samples()))


def sample(sample_id: int):
    """Fetch sample data from server"""
    print(json.dumps(lib.fetch_sample(sample_id)))


def main():
    defopt.run(
        {
            "auth": auth,
            "upload": upload,
            "batches": batches,
            "samples": samples,
            "sample": sample,
        },
        no_negated_flags=True,
        strict_kwonly=False,
        short={},
    )
