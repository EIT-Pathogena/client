import csv

from pathlib import Path

from hostile.lib import clean_paired_fastqs

from gpas_client.models import UploadBatch


def parse_csv(csv_path: Path) -> list[dict]:
    """Parse CSV returning a list of dictionaries"""
    with open(csv_path, "r") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def parse_upload_csv(upload_csv: Path) -> UploadBatch:
    records = parse_csv(upload_csv)
    return UploadBatch(**dict(samples=records))


def upload(upload_csv: Path) -> None:
    upload_csv = Path(upload_csv)
    batch = parse_upload_csv(upload_csv)
    for sample in batch.samples:
        clean_paired_fastqs(
            fastqs=[
                (upload_csv.parent / sample.reads_1, upload_csv.parent / sample.reads_2)
            ],
            force=True,
        )
