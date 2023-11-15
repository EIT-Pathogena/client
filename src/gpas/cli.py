import json
import logging
from getpass import getpass
from pathlib import Path

import defopt

from gpas import lib, util


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
    *,
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
    :arg debug: Enable verbose debug messages
    :arg host: API hostname (for development)
    :arg dry_run: Exit before uploading reads
    """
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)
    host = lib.get_host(host)
    lib.upload(upload_csv, dry_run=dry_run, host=host)


def sample(sample_id: str, host: str | None = None):
    """Fetch sample information"""
    host = lib.get_host(host)
    print(json.dumps(lib.fetch_sample(sample_id, host), indent=4))


def files(sample_id: str, host: str | None = None) -> None:
    """Show latest outputs associated with a sample"""
    host = lib.get_host(host)
    print(json.dumps(lib.list_files(sample_id=sample_id, host=host), indent=4))


def download(
    samples: str,
    *,
    filenames: str = "main_report.json",
    out_dir: Path = Path(),
    host: str | None = None,
    debug: bool = False,
) -> None:
    """
    Download latest outputs associated with a sample

    :arg samples: Comma-separated list of one or more sample IDs, or path of mapping CSV
    :arg filenames: Comma-separated list of one or more filenames to download
    :arg out_dir: Output directory
    :arg host: API hostname (for development)
    :arg debug: Enable verbose debug messages
    """
    host = lib.get_host(host)
    if util.validate_guids(util.parse_comma_separated_string(samples)):
        lib.download(samples=samples, filenames=filenames, out_dir=out_dir, host=host)
    elif Path(samples).is_file():
        lib.download(
            mapping_csv=samples,
            filenames=filenames,
            out_dir=out_dir,
            host=host,
            debug=debug,
        )
    else:
        raise ValueError(
            f"{samples} is neither a valid mapping CSV path nor a comma-separated list of valid GUIDs"
        )


def batches(limit: int = 1000, host: str | None = None):
    """
    List batches on server

    :arg limit: Number of samples to return
    :arg host: API hostname (for development)
    """
    host = lib.get_host(host)
    print(json.dumps(lib.list_batches(host=host, limit=limit), indent=4))


def samples(batch: str, limit: int = 1000, host: str | None = None):
    """
    List samples associated with a batch

    :arg batch_id: Batch ID
    :arg limit: Number of samples to return
    :arg host: API hostname (for development)
    """
    host = lib.get_host(host)
    print(json.dumps(lib.list_samples(batch=batch, host=host, limit=limit), indent=4))


def run(
    *, samples: str | None = None, batch: str | None = None, host: str | None = None
):
    """
    Reanalyse of one or more uploaded samples

    :arg samples: Comma-separated list of sample IDs
    :arg batch: Batch ID
    :arg host: API hostname (for development)
    """
    host = lib.get_host(host)
    if not bool(samples) ^ bool(batch):
        raise ValueError("Specify either samples or batch, not both")
    if samples:
        samples = samples.strip().split(",")
        for sample in samples:
            run_id = lib.run_sample(sample, host=host)
            logging.info(f"Created run_id {run_id} for sample_id {sample}")

    else:
        raise ValueError("Specify either samples or batch")


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
            "run": run,
        },
        no_negated_flags=True,
        strict_kwonly=True,
        short={},
    )
