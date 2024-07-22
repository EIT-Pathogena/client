import logging
from datetime import datetime, date
import json as json_
from os import environ
from pathlib import Path
import sys

import click

from pathogena import lib, util, models
from pathogena.create_upload_csv import build_upload_csv, UploadData


@click.group(name="Pathogena", context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option()
@click.option(
    "--debug", is_flag=True, default=False, help="Enable verbose debug messages"
)
def main(*, debug: bool = False):
    """EIT Pathogena command line interface."""
    lib.check_for_newer_version()
    util.display_cli_version()
    util.configure_debug_logging(debug)


@main.command()
@click.option(
    "--host",
    type=click.Choice(util.DOMAINS.values()),
    default=None,
    help="API hostname (for development)",
)
def auth(
    *,
    host: str | None = None,
) -> None:
    """
    Authenticate with EIT Pathogena.
    """
    host = lib.get_host(host)
    lib.authenticate(host=host)


@main.command()
def autocomplete() -> None:
    """Activate shell completion."""
    shell = environ.get("SHELL", "/bin/bash").split("/")[-1]
    single_use_command = f'eval "$(_PATHOGENA_COMPLETE={shell}_source pathogena)"'
    print(f"Run this command to enable autocompletion:\n    {single_use_command}")
    print(
        f"Add this to your ~/.{shell}rc file to enable this permanently:\n"
        f"    command -v pathogena > /dev/null 2>&1 && {single_use_command}"
    )


@main.command()
@click.argument(
    "input_csv",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
)
@click.option(
    "--output-dir",
    type=click.Path(
        file_okay=False, dir_okay=True, writable=True, exists=True, path_type=Path
    ),
    default=".",
    help="Output directory for the cleaned FastQ files, defaults to the current working directory.",
)
@click.option(
    "--threads",
    type=int,
    default=None,
    help="Number of alignment threads used during decontamination",
)
@click.option(
    "--skip-fastq-check", is_flag=True, help="Skip checking FASTQ files for validity"
)
def decontaminate(
    input_csv: Path,
    *,
    output_dir: Path = Path("."),
    threads: int = None,
    skip_fastq_check: bool = False,
) -> None:
    """
    Decontaminate reads from a CSV file.
    """
    batch = models.create_batch_from_csv(input_csv, skip_fastq_check)
    batch.validate_all_sample_fastqs()
    cleaned_batch_metadata = lib.decontaminate_samples_with_hostile(
        input_csv, batch, threads, output_dir
    )
    batch.update_sample_metadata(metadata=cleaned_batch_metadata)


@main.command()
@click.argument(
    "upload_csv",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
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
@click.option(
    "--host",
    type=click.Choice(util.DOMAINS.values()),
    default=None,
    help="API hostname (for development)",
)
@click.option(
    "--skip-fastq-check", is_flag=True, help="Skip checking FASTQ files for validity"
)
@click.option("--host", type=str, default=None, help="API hostname (for development)")
@click.option(
    "--skip-decontamination",
    is_flag=True,
    default=False,
    help="Run decontamination prior to upload",
)
@click.option(
    "--output-dir",
    type=click.Path(
        file_okay=False, dir_okay=True, writable=True, exists=True, path_type=Path
    ),
    default=".",
    help="Output directory for the cleaned FastQ files, defaults to the current working directory.",
)
def upload(
    upload_csv: Path,
    *,
    threads: int = 1,
    save: bool = False,
    host: str | None = None,
    skip_decontamination: bool = True,
    skip_fastq_check: bool = False,
    output_dir: Path = Path("."),
) -> None:
    """
    Validate, decontaminate and upload reads to EIT Pathogena. Creates a mapping CSV
    file which can be used to download output files with original sample names.
    """
    host = lib.get_host(host)
    lib.check_version_compatibility(host=host)
    if skip_fastq_check and skip_decontamination:
        logging.warning(
            "Cannot skip FastQ checks and decontamination due to metadata requirements for upload, continuing with"
            "checks enabled."
        )
        skip_fastq_check = False
    batch = models.create_batch_from_csv(upload_csv, skip_fastq_check)
    lib.validate_upload_permissions(batch, protocol=lib.get_protocol(), host=host)
    if skip_decontamination:
        batch.validate_all_sample_fastqs()
        batch.update_sample_metadata()
    else:
        cleaned_batch_metadata = lib.decontaminate_samples_with_hostile(
            upload_csv, batch, threads, output_dir=output_dir
        )
        batch.update_sample_metadata(metadata=cleaned_batch_metadata)
    lib.upload_batch(batch=batch, host=host, save=save)


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
    "--output-dir",
    type=click.Path(
        file_okay=False, dir_okay=True, writable=True, exists=True, path_type=Path
    ),
    default=".",
    help="Output directory for the downloaded files.",
)
@click.option(
    "--rename/--no-rename",
    default=True,
    help="Rename downloaded files using sample names when given a mapping CSV",
)
@click.option("--host", type=str, default=None, help="API hostname (for development)")
def download(
    samples: str,
    *,
    filenames: str = "main_report.json",
    inputs: bool = False,
    output_dir: Path = Path(),
    rename: bool = True,
    host: str | None = None,
) -> None:
    """
    Download input and output files associated with sample IDs or a mapping CSV file
    created during upload.
    """
    host = lib.get_host(host)
    if util.validate_guids(util.parse_comma_separated_string(samples)):
        lib.download(
            samples=samples,
            filenames=filenames,
            inputs=inputs,
            out_dir=output_dir,
            host=host,
        )
    elif Path(samples).is_file():
        lib.download(
            mapping_csv=samples,
            filenames=filenames,
            inputs=inputs,
            out_dir=output_dir,
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
def query_raw(samples: str, *, host: str | None = None) -> None:
    """
    Fetch metadata for one or more SAMPLES in JSON format.
    SAMPLES should be command separated list of GUIDs or path to mapping CSV.
    """
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
def query_status(samples: str, *, json: bool = False, host: str | None = None) -> None:
    """
    Fetch processing status for one or more SAMPLES.
    SAMPLES should be command separated list of GUIDs or path to mapping CSV.
    """
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
def validate(upload_csv: Path, *, host: str | None = None) -> None:
    """Validate a given upload CSV."""
    host = lib.get_host(host)
    batch = models.create_batch_from_csv(upload_csv)
    lib.validate_upload_permissions(batch=batch, protocol=lib.get_protocol(), host=host)
    batch.validate_all_sample_fastqs()
    logging.info(f"Successfully validated {upload_csv}")


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
    default=lib.DEFAULT_METADATA["country"],
    show_default=True,
)
@click.option(
    "--instrument-platform",
    type=click.Choice(["illumina", "ont"]),
    default=lib.DEFAULT_METADATA["instrument_platform"],
    help="Sequencing technology",
)
@click.option(
    "--subdivision",
    type=str,
    help="Subdivision",
    default=lib.DEFAULT_METADATA["subdivision"],
    show_default=True,
)
@click.option(
    "--district",
    type=str,
    help="District",
    default=lib.DEFAULT_METADATA["district"],
    show_default=True,
)
@click.option(
    "--ont_read_suffix",
    type=str,
    default=lib.DEFAULT_METADATA["ont_read_suffix"],
    help="Read file ending for ONT fastq files",
    show_default=True,
)
@click.option(
    "--illumina_read1_suffix",
    type=str,
    default=lib.DEFAULT_METADATA["illumina_read1_suffix"],
    help="Read file ending for Illumina read 1 files",
    show_default=True,
)
@click.option(
    "--illumina_read2_suffix",
    type=str,
    default=lib.DEFAULT_METADATA["illumina_read2_suffix"],
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
    subdivision: str = lib.DEFAULT_METADATA["subdivision"],
    district: str = lib.DEFAULT_METADATA["district"],
    pipeline: str = lib.DEFAULT_METADATA["pipeline"],
    host_organism: str = "homo sapiens",
    ont_read_suffix: str = lib.DEFAULT_METADATA["ont_read_suffix"],
    illumina_read1_suffix: str = lib.DEFAULT_METADATA["illumina_read1_suffix"],
    illumina_read2_suffix: str = lib.DEFAULT_METADATA["illumina_read2_suffix"],
    max_batch_size: int = lib.DEFAULT_METADATA["max_batch_size"],
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


if __name__ == "__main__":
    main(sys.argv[1:])