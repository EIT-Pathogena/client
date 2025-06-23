import csv
import logging
from pathlib import Path

import httpx
from hostile.lib import clean_fastqs, clean_paired_fastqs
from hostile.util import choose_default_thread_count
from pydantic import Field

from pathogena import models, util
from pathogena.constants import (
    CPU_COUNT,
    HOSTILE_INDEX_NAME,
)
from pathogena.log_utils import httpx_hooks
from pathogena.models import UploadBase, UploadBatch, UploadData

logging.getLogger("httpx").setLevel(logging.WARNING)


def decontaminate_samples_with_hostile(
    batch: models.UploadBatch,
    threads: int,
    output_dir: Path = Path("."),
) -> dict:
    """Run Hostile to remove human reads from a given CSV file of FastQ files and return metadata related to the batch.

    Args:
        batch (models.UploadBatch): The batch of samples to decontaminate.
        threads (int): The number of threads to use.
        output_dir (Path): The output directory for the cleaned FastQ files.

    Returns:
        dict: Metadata related to the batch.
    """
    logging.debug(f"decontaminate_samples_with_hostile() {threads=} {output_dir=}")
    logging.info(
        f"Removing human reads from {str(batch.instrument_platform).upper()} FastQ files and storing in {output_dir.absolute()}"
    )
    decontamination_metadata = {}
    if batch.is_ont():
        decontamination_metadata = clean_fastqs(
            fastqs=[sample.reads_1_resolved_path for sample in batch.samples],
            index=HOSTILE_INDEX_NAME,
            rename=True,
            reorder=True,
            threads=threads if threads else choose_default_thread_count(CPU_COUNT),
            out_dir=output_dir,
            force=True,
        )
    elif batch.is_illumina():
        decontamination_metadata = clean_paired_fastqs(
            fastqs=[
                (sample.reads_1_resolved_path, sample.reads_2_resolved_path)
                for sample in batch.samples
            ],
            index=HOSTILE_INDEX_NAME,
            rename=True,
            reorder=True,
            threads=threads if threads else choose_default_thread_count(CPU_COUNT),
            out_dir=output_dir,
            force=True,
            aligner_args=" --local",
        )
    batch_metadata = dict(
        zip(
            [s.sample_name for s in batch.samples],
            decontamination_metadata,
            strict=False,
        )
    )
    batch.ran_through_hostile = True
    logging.info(
        f"Human reads removed from input samples and can be found here: {output_dir.absolute()}"
    )
    return batch_metadata


def validate_upload_permissions(batch: UploadBatch, protocol: str, host: str) -> None:
    """Perform pre-submission validation of a batch of sample model subsets.

    Args:
        batch (UploadBatch): The batch to validate.
        protocol (str): The protocol to use.
        host (str): The host server.
    """
    data = []
    for sample in batch.samples:
        data.append(
            {
                "collection_date": str(sample.collection_date),
                "country": sample.country,
                "subdivision": sample.subdivision,
                "district": sample.district,
                "instrument_platform": sample.instrument_platform,
                "specimen_organism": sample.specimen_organism,
            }
        )
    logging.debug(f"Validating {data=}")
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    with httpx.Client(
        event_hooks=httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
        timeout=60,
    ) as client:
        response = client.post(
            f"{protocol}://{host}/api/v1/batches/validate",
            headers=headers,
            json=data,
            follow_redirects=True,
        )
    logging.debug(f"{response.json()=}")


def build_upload_csv(
    samples_folder: Path | str,
    output_csv: Path | str,
    upload_data: UploadData,
) -> None:
    """Create upload csv based on folder of fastq files.

    Args:
        samples_folder (Path | str): The folder containing the FASTQ files.
        output_csv (Path | str): The path to the output CSV file.
        upload_data (UploadData): The upload data containing read suffixes and batch size.
    """
    samples_folder = Path(samples_folder)
    output_csv = Path(output_csv)
    assert samples_folder.is_dir()  # This should be dealt with by Click

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

        files = [
            (g, str(f1), str(f2))
            for g, f1, f2 in zip(guids1, fastqs1, fastqs2, strict=False)
        ]
    elif upload_data.instrument_platform == "ont":
        fastqs = list(samples_folder.glob(f"*{upload_data.ont_read_suffix}"))
        fastqs.sort()
        guids = [f.name.replace(upload_data.ont_read_suffix, "") for f in fastqs]
        files = [(g, str(f), "") for g, f in zip(guids, fastqs, strict=False)]
    else:
        raise ValueError("Invalid instrument platform")

    if (
        upload_data.specimen_organism
        not in UploadData.model_fields["specimen_organism"].annotation.__args__
    ):
        raise ValueError("Invalid pipeline")

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
    logging.info(
        "You can use `pathogena validate` to check the CSV files before uploading."
    )


def chunks(lst: list, n: int) -> list[list]:
    """Yield successive n-sized chunks from provided list.

    Args:
        lst (list): The list to split.
        n (int): The size of each chunk.

    Returns:
        list[list]: A list of chunks.
    """
    return [lst[i : i + n] for i in range(0, len(lst), n)]


def _write_csv(
    filename: Path,
    read_files: list[tuple[str, str, str]],
    upload_data: UploadData,
) -> None:
    """Build a CSV file for upload to EIT Pathogena.

    Args:
        data (list[dict]): The data to write.
        output_csv (Path): The path to the output CSV file.
    """
    use_amplicon_scheme = upload_data.specimen_organism == "sars-cov-2"
    if upload_data.amplicon_scheme is None:
        logging.warning(
            f"No amplicon scheme has been specified, automatic detection will be used."
        )
        logging.warning(
            "Note that selecting automatic detection may occasionally result in misclassification "
            "during sample analysis."
        )

    # Note that csv module uses CRLF line endings
    with open(filename, "w", newline="", encoding="utf-8") as outfile:
        fieldnames = [
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
        if use_amplicon_scheme:
            fieldnames.append("amplicon_scheme")
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for sample, f1, f2 in read_files:
            row = {
                "batch_name": upload_data.batch_name,
                "sample_name": sample,
                "reads_1": f1,
                "reads_2": f2,
                "control": "",
                "collection_date": upload_data.collection_date,
                "country": upload_data.country,
                "subdivision": upload_data.subdivision,
                "district": upload_data.district,
                "specimen_organism": upload_data.specimen_organism,
                "host_organism": upload_data.host_organism,
                "instrument_platform": upload_data.instrument_platform,
            }
            if use_amplicon_scheme:
                row["amplicon_scheme"] = upload_data.amplicon_scheme
            writer.writerow(row)
