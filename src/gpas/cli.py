import json as json_
from getpass import getpass
from pathlib import Path

import defopt

from gpas import lib, util


def auth(
    *,
    host: str | None = None,
) -> None:
    """
    Authenticate with the GPAS platform.

    :arg host: API hostname
    """
    host = lib.get_host(host)
    username = input("Enter your username: ")
    password = getpass(prompt="Enter your password: ")
    lib.authenticate(username=username, password=password, host=host)


def upload(
    upload_csv: Path,
    *,
    # out_dir: Path = Path(),
    threads: int | None = None,
    # save_reads: bool = False,
    dry_run: bool = False,
    host: str | None = None,
    debug: bool = False,
) -> None:
    """
    Validate, decontaminate and upload reads to the GPAS platform. Creates a mapping CSV
    file which can be used to download output files with original sample names.

    :arg upload_csv: Path of upload csv
    :arg threads: Number of alignment threads used during decontamination
    :arg debug: Enable verbose debug messages
    :arg host: API hostname
    :arg dry_run: Exit before uploading reads
    """
    # :arg out_dir: Path of directory in which to save mapping CSV
    # :arg save_reads: Save decontaminated reads in out_dir
    util.configure_debug_logging(debug)
    host = lib.get_host(host)
    lib.upload(upload_csv, threads=threads, dry_run=dry_run, host=host)


def download(
    samples: str,
    *,
    filenames: str = "main_report.json",
    inputs: bool = False,
    out_dir: Path = Path(),
    rename: bool = True,
    host: str | None = None,
    debug: bool = False,
) -> None:
    """
    Download input and output files associated with sample IDs or a mapping CSV file
    created during upload.

    :arg samples: Comma-separated list of sample IDs or the path of a mapping CSV
    :arg filenames: Comma-separated list of output filenames to download
    :arg inputs: Also download decontaminated input FASTQ file(s)
    :arg out_dir: Output directory
    :arg rename: Rename downloaded files using sample names when given a mapping CSV
    :arg host: API hostname
    :arg debug: Enable verbose debug messages
    """
    util.configure_debug_logging(debug)
    host = lib.get_host(host)
    if util.validate_guids(util.parse_comma_separated_string(samples)):
        lib.download(
            samples=samples,
            filenames=filenames,
            inputs=inputs,
            out_dir=out_dir,
            host=host,
        )
    elif Path(samples).is_file():
        lib.download(
            mapping_csv=samples,
            filenames=filenames,
            inputs=inputs,
            out_dir=out_dir,
            rename=rename,
            host=host,
            debug=debug,
        )
    else:
        raise ValueError(
            f"{samples} is neither a valid mapping CSV path nor a comma-separated list of valid GUIDs"
        )


def query_raw(samples: str, *, host: str | None = None, debug: bool = False) -> None:
    """
    Fetch metadata for one or more samples in JSON format.

    :arg samples: Comma-separated list of sample IDs or the path of a mapping CSV
    :arg host: API hostname (for development)
    :arg debug: Enable verbose debug messages
    """
    util.configure_debug_logging(debug)
    host = lib.get_host(host)
    if util.validate_guids(util.parse_comma_separated_string(samples)):
        result = lib.query(samples=samples, host=host)
    elif Path(samples).is_file():
        result = lib.query(mapping_csv=samples, host=host)
    else:
        raise ValueError(
            f"{samples} is neither a valid mapping CSV path nor a comma-separated list of valid GUIDs"
        )
    print(json_.dumps(result, indent=4))


def query_status(
    samples: str, *, json: bool = False, host: str | None = None, debug: bool = False
) -> None:
    """
    Fetch processing status for one or more samples

    :arg samples: Comma-separated list of sample IDs or the path of a mapping CSV
    :arg host: API hostname
    :arg debug: Enable verbose debug messages
    """
    util.configure_debug_logging(debug)
    host = lib.get_host(host)
    if util.validate_guids(util.parse_comma_separated_string(samples)):
        result = lib.status(samples=samples, host=host)
    elif Path(samples).is_file():
        result = lib.status(mapping_csv=samples, host=host)
    else:
        raise ValueError(
            f"{samples} is neither a valid mapping CSV path nor a comma-separated list of valid GUIDs"
        )
    if json:
        print(json_.dumps(result, indent=4))
    else:
        for name, status in result.items():
            print(f"{name} \t{status}")


# def run(
#     *, samples: str | None = None, batch: str | None = None, host: str | None = None
# ):
#     """
#     Reanalyse of one or more uploaded samples

#     :arg samples: Comma-separated list of sample IDs
#     :arg batch: Batch ID
#     :arg host: API hostname
#     """
#     host = lib.get_host(host)
#     if not bool(samples) ^ bool(batch):
#         raise ValueError("Specify either samples or batch, not both")
#     if samples:
#         samples = samples.strip().split(",")
#         for sample in samples:
#             run_id = lib.run_sample(sample, host=host)
#             logging.info(f"Created run_id {run_id} for sample_id {sample}")

#     else:
#         raise ValueError("Specify either samples or batch")


def main() -> None:
    defopt.run(
        {
            "auth": auth,
            "upload": upload,
            "download": download,
            "query": {"raw": query_raw, "status": query_status},
            # "run": run,
        },
        no_negated_flags=True,
        strict_kwonly=True,
        short={},
    )
