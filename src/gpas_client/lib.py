import csv

from pathlib import Path

import hostile

from gpas_client.models import Batch, Sample


def parse_csv(csv_path: Path) -> list[dict]:
    """Parse CSV returning a list of dictionaries"""
    with open(csv_path, "r") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def parse_upload_csv(upload_csv: Path) -> Batch:
    records = parse_csv(upload_csv)
    return Batch(**dict(samples=records))


def upload(upload_csv: Path) -> None:
    batch = parse_upload_csv(upload_csv)
