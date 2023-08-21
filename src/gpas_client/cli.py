import json
import logging
from getpass import getpass
from pathlib import Path

import defopt

from gpas_client import lib


def auth():
    username = input("Enter your username: ")
    password = getpass(prompt="Enter your password: ")
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
    else:
        logging.getLogger().setLevel(logging.INFO)
    lib.upload(upload_csv, dry_run=dry_run)


def sample(sample_id: int):
    """Fetch sample information"""
    print(json.dumps(lib.fetch_sample(sample_id), indent=4))


def files(sample_id: int) -> None:
    """Show latest outputs associated with a sample"""
    print(json.dumps(lib.list_files(sample_id), indent=4))


def download(sample_id: int) -> None:
    """Download latest outputs associated with a sample"""
    lib.download(sample_id)


def batches():
    """List batches on server"""
    print(json.dumps(lib.list_batches()))


def samples():
    """List samples on server"""
    print(json.dumps(lib.list_samples(), indent=4))


def main():
    defopt.run(
        {
            "auth": auth,
            "batches": batches,
            "samples": samples,
            "sample": sample,
            "files": files,
            "upload": upload,
            "download": download,
        },
        no_negated_flags=True,
        strict_kwonly=False,
        short={},
    )
