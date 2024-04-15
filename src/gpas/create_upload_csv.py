from pathlib import Path
import logging
import csv

from pydantic import Field
from gpas.models import UploadBase


class UploadData(UploadBase):
    ont_read_suffix: str = Field(
        default=".fastq.gz", description="Suffix for ONT reads"
    )
    illumina_read1_suffix: str = Field(
        default="_1.fastq.gz", description="Suffix for Illumina reads (first of pair)"
    )
    illumina_read2_suffix: str = Field(
        default="_2.fastq.gz", description="Suffix for Illumina reads (second of pair)"
    )
    max_batch_size: int = Field(
        default=50, description="Maximum number of samples per batch"
    )


def build_upload_csv(
    samples_folder: Path | str,
    output_csv: Path | str,
    upload_data: UploadData,
):
    """Create upload csv based on folder of fastq files."""
    samples_folder = Path(samples_folder)
    output_csv = Path(output_csv)
    assert samples_folder.is_dir()  # This should be dealth with by Click

    if upload_data.instrument_platform == "illumina":
        if upload_data.illumina_read1_suffix == upload_data.illumina_read2_suffix:
            raise ValueError("Must have different reads suffixes")

        fastqs1 = list(samples_folder.glob(f"*{upload_data.illumina_read1_suffix}"))
        fastqs2 = list(samples_folder.glob(f"*{upload_data.illumina_read2_suffix}"))

        # sort the lists alphabetically to ensure the files are paired correctly
        fastqs1.sort()
        fastqs2.sort()
        guids1 = [
            f.name.replace(upload_data.illumina_read1_suffix, "") for f in fastqs1
        ]
        guids2 = {
            f.name.replace(upload_data.illumina_read2_suffix, "") for f in fastqs2
        }
        unmatched = guids2.symmetric_difference(guids1)

        if unmatched:
            raise ValueError(
                f"Each sample must have two paired files.\nSome lack pairs:{unmatched}"
            )

        files = [(g, str(f1), str(f2)) for g, f1, f2 in zip(guids1, fastqs1, fastqs2)]
    elif upload_data.instrument_platform == "ont":
        fastqs = list(samples_folder.glob(f"*{upload_data.ont_read_suffix}"))
        fastqs.sort()
        guids = [f.name.replace(upload_data.ont_read_suffix, "") for f in fastqs]
        files = [(g, str(f), str("")) for g, f in zip(guids, fastqs)]
    else:
        raise ValueError("Invalid instrument platform")

    if upload_data.max_batch_size >= len(files):
        _write_csv(
            output_csv,
            files,
            upload_data,
        )
        output_csvs = [output_csv]
    else:
        output_csvs = []
        for i, chunk in enumerate(chunks(files, upload_data.max_batch_size), start=1):
            output_csvs.append(
                output_csv.with_name(f"{output_csv.stem}_{i}{output_csv.suffix}")
            )
            _write_csv(
                output_csv.with_name(f"{output_csv.stem}_{i}{output_csv.suffix}"),
                chunk,
                upload_data,
            )
    logging.info(
        f"Created {len(output_csvs)} CSV files: {', '.join([csv.name for csv in output_csvs])}"
    )
    logging.info("You can use `gpas validate` to check the CSV files before uploading.")


def chunks(lst: list, n: int) -> list[list]:
    """
    Yield successive n-sized chunks from provided list.
    """
    return [lst[i : i + n] for i in range(0, len(lst), n)]


def _write_csv(
    filename: Path,
    read_files: list[tuple[str, str, str]],
    upload_data: UploadData,
):
    """
    Build a CSV file for upload to the Genomic Pathogen Analysis System (GPAS).
    """
    # Note that csv module uses CRLF line endings
    with open(filename, "w", newline="", encoding="utf-8") as outfile:
        csv_writer = csv.writer(outfile)
        csv_writer.writerow(
            [
                "batch_name",
                "sample_name",
                "reads_1",
                "reads_2",
                "control",
                "collection_date",
                "country",
                "subdivision",
                "district",
                "specimen_organism",
                "host_organism",
                "instrument_platform",
            ]
        )
        for sample, f1, f2 in read_files:
            csv_writer.writerow(
                [
                    upload_data.batch_name,
                    sample,
                    f1,
                    f2,
                    "",
                    upload_data.collection_date,
                    upload_data.country,
                    upload_data.subdivision,
                    upload_data.district,
                    upload_data.specimen_organism,
                    upload_data.host_organism,
                    upload_data.instrument_platform,
                ]
            )
