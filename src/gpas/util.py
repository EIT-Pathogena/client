import csv
import hashlib
import json
import logging
import random
import string

from pathlib import Path
from urllib.parse import urlparse

import httpx

from gpas.models import UploadBatch, UploadSample


def log_request(request):
    logging.debug(f"Request: {request.method} {request.url}")


def log_response(response):
    request = response.request
    logging.debug(f"Response: {request.method} {request.url} ({response.status_code})")
    logging.debug(f"Response: {request.method} {request.url} ({response.status_code})")


def raise_for_status(response):
    response.raise_for_status()


httpx_hooks = {"request": [log_request], "response": [log_response, raise_for_status]}


def generate_identifier(length=6):
    letters_and_digits = string.ascii_letters + string.digits
    random_identifier = "".join(
        random.choice(letters_and_digits) for _ in range(length)
    )
    return random_identifier.lower()


def get_host_name(url) -> str:
    parsed_uri = urlparse(url)
    return parsed_uri.hostname


def get_access_token(host="https://dev.portal.gpas.world/api") -> str:
    """Reads token from ~/.config/gpas/tokens/<host>"""
    host_name = get_host_name(host)
    token_path = Path.home() / ".config" / "gpas" / "tokens" / f"{host_name}.json"
    logging.debug(f"{token_path=}")
    data = json.loads((token_path).read_text())
    return data["access_token"].strip()


def parse_csv(csv_path: Path) -> list[dict]:
    """Parse CSV returning a list of dictionaries"""
    with open(csv_path, "r") as fh:
        reader = csv.DictReader(fh)
        return [row for row in reader]


def parse_upload_csv(upload_csv: Path) -> UploadBatch:
    records = parse_csv(upload_csv)
    return UploadBatch(  # Include upload_csv to enable relative fastq path validation
        samples=[UploadSample(**r, **dict(upload_csv=upload_csv)) for r in records]
    )


def write_csv(records: list[dict], file_name: Path | str) -> None:
    """Write a list of dictionaries to a CSV file"""
    with open(file_name, "w", newline="") as fh:
        fieldnames = records[0].keys()
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r)


def hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(16_384), b""):
            hasher.update(block)
    return hasher.hexdigest()


def upload_file(sample_id: int, file_path: Path) -> None:
    with httpx.Client(
        timeout=600, event_hooks=httpx_hooks
    ) as client:  # 10 minute timeout
        with open(file_path, "rb") as fh:
            client.post(
                f"https://dev.portal.gpas.world/api/v1/samples/{sample_id}/files",
                headers={f"Authorization": f"Bearer {get_access_token()}"},
                files={"file": fh},
            )


def upload_paired_fastqs(sample_id: int, reads_1: Path, reads_2: Path) -> None:
    """Upload paired FASTQ files to server in parallel"""

    reads_1, reads_2 = Path(reads_1), Path(reads_2)
    upload_file(sample_id, reads_1)
    upload_file(sample_id, reads_2)
    # with concurrent.futures.ThreadPoolExecutor(max_workers=2) as x:
    #     futures = [
    #         x.submit(upload_file, sample_id, reads_1),
    #         x.submit(upload_file, sample_id, reads_2),
    #     ]
    #     for future in concurrent.futures.as_completed(futures):
    #         future.result()
