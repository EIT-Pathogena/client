import json
import logging
from getpass import getpass
from pathlib import Path

import defopt

from gpas import lib


def auth(
    *,
    host: str | None = None,
) -> None:
    """
    Authenticate with GPAS

    :arg host: API hostname (for development)
    """
    host = lib.get_host(host)
    username = input("Enter your username: ")
    password = getpass(prompt="Enter your password: ")
    lib.authenticate(username=username, password=password, host=host)


def upload(
    upload_csv: Path,
    out_dir: Path = Path(),
    threads: int = 0,
    save_reads: bool = False,
    dry_run: bool = False,
    host: str | None = None,
    debug: bool = False,
):
    """
    Validate, decontaminate and upload reads to the GPAS platform

    :arg upload_csv: Path of upload csv
    :arg out_dir: Path of directory in which to save mapping CSV
    :arg save_reads: Save decontaminated reads in out_dir
    :arg threads: Number of threads used in decontamination
    :arg debug: Emit verbose debug messages
    :arg host: API hostname (for development)
    :arg dry_run: Exit before uploading reads
    """
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)
    host = lib.get_host(host)
    lib.upload(upload_csv, dry_run=dry_run, host=host)


def sample(sample_id: int, host: str | None = None):
    """Fetch sample information"""
    host = lib.get_host(host)
    print(json.dumps(lib.fetch_sample(sample_id, host), indent=4))


def files(sample_id: int, host: str | None = None) -> None:
    """Show latest outputs associated with a sample"""
    host = lib.get_host(host)
    print(json.dumps(lib.list_files(sample_id=sample_id, host=host), indent=4))


def download(
    sample_id: int, filename: Path, out_dir: Path = Path(), host: str | None = None
) -> None:
    """
    Download latest outputs associated with a sample

    :arg sample_id: Sample ID
    :arg filename: Name of file to download
    :arg out_dir: Output directory
    :arg host: API hostname (for development)
    """
    host = lib.get_host(host)
    lib.download(sample_id=sample_id, filename=filename, host=host)


def batches(host: str | None = None):
    """List batches on server"""
    host = lib.get_host(host)
    print(json.dumps(lib.list_batches(host)))


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
