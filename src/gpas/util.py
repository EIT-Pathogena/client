import csv
import hashlib
import json
import logging
import os
import uuid

from pathlib import Path
from typing import Literal

import httpx


PLATFORMS = Literal["illumina", "ont"]


def configure_debug_logging(debug: bool):
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)


def log_request(request):
    logging.debug(f"Request: {request.method} {request.url}")


def log_response(response):
    if response.is_error:
        request = response.request
        response.read()
        logging.error(
            f"{request.method} {request.url} ({response.status_code}) response:\n{json.dumps(response.json(), indent=4)}"
        )


def raise_for_status(response):
    response.raise_for_status()


httpx_hooks = {"request": [log_request], "response": [log_response, raise_for_status]}


def get_access_token(host: str) -> str:
    """Reads token from ~/.config/gpas/tokens/<host>"""
    token_path = Path.home() / ".config" / "gpas" / "tokens" / f"{host}.json"
    logging.debug(f"{token_path=}")
    try:
        data = json.loads((token_path).read_text())
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Token not found at {token_path}, have you authenticated?"
        )
    return data["access_token"].strip()


def parse_csv(csv_path: Path) -> list[dict]:
    """Parse CSV returning a list of dictionaries"""
    with open(csv_path, "r") as fh:
        reader = csv.DictReader(fh)
        return [row for row in reader]


def write_csv(records: list[dict], file_name: Path | str) -> None:
    """Write a list of dictionaries to a CSV file"""
    with open(file_name, "w", newline="") as fh:
        fieldnames = records[0].keys()
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r)


def hash_file(file_path: Path) -> str:
    hasher = hashlib.sha256()
    CHUNK_SIZE = 1_048_576  # 2**20, 1MiB
    with open(Path(file_path), "rb") as fh:
        while chunk := fh.read(CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def upload_file(
    sample_id: int, file_path: Path, host: str, protocol: str, checksum: str
) -> None:
    with httpx.Client(
        event_hooks=httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
        timeout=7200,  # 2 hours
    ) as client:
        with open(file_path, "rb") as fh:
            client.post(
                f"{protocol}://{host}/api/v1/samples/{sample_id}/files",
                headers={"Authorization": f"Bearer {get_access_token(host)}"},
                files={"file": fh},
                data={"checksum": checksum},
            )


def upload_fastq(
    sample_id: int,
    sample_name: str,
    reads: Path,
    host: str,
    protocol: str,
) -> None:
    """Upload FASTQ file to server"""
    reads = Path(reads)
    logging.debug(f"upload_fastq(): {sample_id=}, {sample_name=}, {reads=}")
    logging.info(f"Uploading {sample_name}")
    checksum = hash_file(reads)
    upload_file(sample_id, reads, host=host, protocol=protocol, checksum=checksum)
    logging.info(f"  Uploaded {reads.name}")


def upload_paired_fastqs(
    sample_id: int,
    sample_name: str,
    reads_1: Path,
    reads_2: Path,
    host: str,
    protocol: str,
) -> None:
    """Upload paired FASTQ files to server"""
    reads_1, reads_2 = Path(reads_1), Path(reads_2)
    logging.debug(
        f"upload_paired_fastqs(): {sample_id=}, {sample_name=}, {reads_1=}, {reads_2=}"
    )
    logging.info(f"Uploading {sample_name}")
    checksum1 = hash_file(reads_1)
    checksum2 = hash_file(reads_2)
    upload_file(sample_id, reads_1, host=host, protocol=protocol, checksum=checksum1)
    logging.info(f"  Uploaded {reads_1.name}")
    upload_file(sample_id, reads_2, host=host, protocol=protocol, checksum=checksum2)
    logging.info(f"  Uploaded {reads_2.name}")

    # with concurrent.futures.ThreadPoolExecutor(max_workers=2) as x:
    #     futures = [
    #         x.submit(upload_file, sample_id, reads_1),
    #         x.submit(upload_file, sample_id, reads_2),
    #     ]
    #     for future in concurrent.futures.as_completed(futures):
    #         future.result()


def parse_comma_separated_string(string) -> set[str]:
    return set(string.strip(",").split(","))


def validate_guids(guids: list[str]) -> bool:
    for guid in guids:
        try:
            uuid.UUID(str(guid))
            return True
        except ValueError:
            return False


def map_control_value(v: str) -> bool | None:
    return {"positive": True, "negative": False, "": None}.get(v)


def is_dev_mode() -> bool:
    return True if "GPAS_DEV_MODE" in os.environ else False
