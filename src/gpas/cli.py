from datetime import datetime, date
import json as json_
from getpass import getpass
from pathlib import Path

import click

from gpas import lib, util
from gpas.create_upload_csv import build_upload_csv, UploadData


@click.group(name="GPAS")
@click.version_option()
@click.help_option("-h", "--help")
def main():
    """GPAS command line interface."""
    pass


@main.command()
@click.option("--host", type=str, default=None, help="API hostname (for development)")
def auth(
    *,
    host: str | None = None,
) -> None:
    """
    Authenticate with the GPAS platform.
    """
    host = lib.get_host(host)
    username = input("Enter your username: ")
    password = getpass(prompt="Enter your password: ")
    lib.authenticate(username=username, password=password, host=host)


@main.command()
@click.argument(
    "upload_csv", type=click.Path(exists=True, dir_okay=False, readable=True)
)
@click.option(
    "--threads",
    type=int,
    default=None,
    help="Number of alignment threads used during decontamination",
)
@click.option(
    "--save", is_flag=True, help="Retain decontaminated reads after upload completion"
)
@click.option("--dry-run", is_flag=True, help="Exit before uploading reads")
@click.option("--host", type=str, default=None, help="API hostname (for development)")
@click.option("--debug", is_flag=True, help="Enable verbose debug messages")
def upload(
    upload_csv: Path,
    *,
    # out_dir: Path = Path(),
    threads: int | None = None,
    save: bool = False,
    dry_run: bool = False,
    host: str | None = None,
    debug: bool = False,
) -> None:
    """
    Validate, decontaminate and upload reads to the GPAS platform. Creates a mapping CSV
    file which can be used to download output files with original sample names.
    """
    # :arg out_dir: Path of directory in which to save mapping CSV
    util.configure_debug_logging(debug)
    host = lib.get_host(host)
    lib.upload(upload_csv, save=save, dry_run=dry_run, threads=threads, host=host)


@main.command()
@click.argument("samples", type=str)
@click.option(
    "--filenames",
    type=str,
    default="main_report.json",
    help="Comma-separated list of output filenames to download",
)
@click.option(
    "--inputs", is_flag=True, help="Also download decontaminated input FASTQ file(s)"
)
@click.option(
    "--out-dir", type=click.Path(file_okay=False), default=".", help="Output directory"
)
@click.option(
    "--rename/--no-rename",
    default=True,
    help="Rename downloaded files using sample names when given a mapping CSV",
)
@click.option("--host", type=str, default=None, help="API hostname (for development)")
@click.option("--debug", is_flag=True, help="Enable verbose debug messages")
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
        )
    else:
        raise ValueError(
            f"{samples} is neither a valid mapping CSV path nor a comma-separated list of valid GUIDs"
        )


@main.command()
@click.argument("samples", type=str)
@click.option("--host", type=str, default=None, help="API hostname (for development)")
@click.option("--debug", is_flag=True, help="Enable verbose debug messages")
def query_raw(samples: str, *, host: str | None = None, debug: bool = False) -> None:
    """
    Fetch metadata for one or more SAMPLES in JSON format.
    SAMPLES should be command separated list of GUIDs or path to mapping CSV.
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


@main.command()
@click.argument("samples", type=str)
@click.option("--json", is_flag=True, help="Output status in JSON format")
@click.option("--host", type=str, default=None, help="API hostname (for development)")
@click.option("--debug", is_flag=True, help="Enable verbose debug messages")
def query_status(
    samples: str, *, json: bool = False, host: str | None = None, debug: bool = False
) -> None:
    """
    Fetch processing status for one or more SAMPLES.
    SAMPLES should be command separated list of GUIDs or path to mapping CSV.
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


@main.command()
def download_index() -> None:
    """
    Download and cache host decontamination index.
    """
    lib.download_index()


@main.command()
@click.argument(
    "upload_csv", type=click.Path(exists=True, dir_okay=False, readable=True)
)
@click.option("--host", type=str, default=None, help="API hostname (for development)")
@click.option("--debug", is_flag=True, help="Enable verbose debug messages")
def validate(upload_csv: Path, *, host: str | None = None, debug: bool = False) -> None:
    """Validate a given upload CSV."""
    util.configure_debug_logging(debug)
    host = lib.get_host(host)
    lib.validate(upload_csv, host=host)


# In future this could be updated based on a file
defaults = {
    "country": None,
    "district": "",
    "subdivision": "",
    "instrument_platform": "illumina",
    "ont_read_suffix": ".fastq.gz",
    "illumina_read1_suffix": "_1.fastq.gz",
    "illumina_read2_suffix": "_2.fastq.gz",
    "max_batch_size": 50,
}


@main.command()
@click.argument(
    "samples-folder", type=click.Path(exists=True, file_okay=False), required=True
)
@click.option(
    "--output-csv",
    type=click.Path(dir_okay=False),
    default="upload.csv",
    help="Path to output CSV file",
    required=True,
)
@click.option("--batch-name", type=str, help="Batch name", required=True)
@click.option(
    "--collection-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=str(date.today()),
    show_default=True,
    help="Collection date (YYYY-MM-DD)",
    required=True,
)
@click.option(
    "--country",
    type=str,
    help="3-letter Country Code",
    required=True,
    default=defaults["country"],
    show_default=True,
)
@click.option(
    "--instrument-platform",
    type=click.Choice(["illumina", "ont"]),
    default=defaults["instrument_platform"],
    help="Sequencing technology",
)
@click.option(
    "--subdivision",
    type=str,
    help="Subdivision",
    default=defaults["subdivision"],
    show_default=True,
)
@click.option(
    "--district",
    type=str,
    help="District",
    default=defaults["district"],
    show_default=True,
)
@click.option(
    "--ont_read_suffix",
    type=str,
    default=defaults["ont_read_suffix"],
    help="Read file ending for ONT fastq files",
    show_default=True,
)
@click.option(
    "--illumina_read1_suffix",
    type=str,
    default=defaults["illumina_read1_suffix"],
    help="Read file ending for Illumina read 1 files",
    show_default=True,
)
@click.option(
    "--illumina_read2_suffix",
    type=str,
    default=defaults["illumina_read2_suffix"],
    help="Read file ending for Illumina read 2 files",
    show_default=True,
)
@click.option("--max-batch-size", type=int, default=50, show_default=True)
def build_csv(
    samples_folder: Path,
    output_csv: Path,
    instrument_platform: str,
    batch_name: str,
    collection_date: datetime,
    country: str,
    subdivision: str = "",
    district: str = "",
    pipeline: str = "mycobacteria",
    host_organism: str = "homo sapiens",
    ont_read_suffix: str = ".fastq.gz",
    illumina_read1_suffix: str = "_1.fastq.gz",
    illumina_read2_suffix: str = "_2.fastq.gz",
    max_batch_size: int = 50,
):
    """
    Command to create upload csv from SAMPLES_FOLDER containing sample fastqs.\n
    Use max_batch_size to split into multiple separate upload csvs.\n
    Adjust the read_suffix parameters to match the file endings for your read files.
    """
    if len(country) != 3:
        raise ValueError(f"Country ({country}) should be 3 letter code")
    output_csv = Path(output_csv)
    samples_folder = Path(samples_folder)

    upload_data = UploadData(
        batch_name=batch_name,
        instrument_platform=instrument_platform,  # type: ignore
        collection_date=collection_date,
        country=country,
        subdivision=subdivision,
        district=district,
        specimen_organism=pipeline,  # type: ignore
        host_organism=host_organism,
        ont_read_suffix=ont_read_suffix,
        illumina_read1_suffix=illumina_read1_suffix,
        illumina_read2_suffix=illumina_read2_suffix,
        max_batch_size=max_batch_size,
    )

    build_upload_csv(
        samples_folder,
        output_csv,
        upload_data,
    )
