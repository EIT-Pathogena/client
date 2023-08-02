import csv
import json
import logging
import random
import string

from urllib.parse import urlparse

from pathlib import Path

import httpx
from hostile.lib import clean_paired_fastqs

from gpas_client.models import UploadBatch


def generate_random_identifier(length=8):
    letters_and_digits = string.ascii_letters + string.digits
    random_identifier = "".join(
        random.choice(letters_and_digits) for _ in range(length)
    )
    return random_identifier


def get_host_name(url) -> str:
    parsed_uri = urlparse(url)
    return parsed_uri.hostname


def authenticate(
    username: str, password: str, host="https://dev.portal.gpas.world/api"
) -> None:
    """Requests, writes auth token to ~/.config/gpas/tokens/<host>"""
    host_name = get_host_name(host)
    logging.info(f"{username=} {password=}")
    response = httpx.post(
        f"{host}/v1/auth/token",
        json={"username": username, "password": password},
    )
    response.raise_for_status()
    data = response.json()
    conf_dir = Path.home() / ".config" / "gpas"
    token_dir = conf_dir / "tokens"
    token_dir.mkdir(parents=True, exist_ok=True)
    with open(token_dir / f"{host_name}.json", "w") as fh:
        json.dump(data, fh)


def get_access_token(host="https://dev.portal.gpas.world/api") -> str:
    """Reads token from ~/.config/gpas/tokens/<host>"""
    host_name = get_host_name(host)
    token_path = Path.home() / ".config" / "gpas" / "tokens" / f"{host_name}.json"
    logging.info(f"{token_path=}")
    data = json.loads((token_path).read_text())
    return data["access_token"].strip()


def parse_csv(csv_path: Path) -> list[dict]:
    """Parse CSV returning a list of dictionaries"""
    with open(csv_path, "r") as fh:
        reader = csv.DictReader(fh)
        print(reader)
        return [row for row in reader]


def parse_upload_csv(upload_csv: Path) -> UploadBatch:
    records = parse_csv(upload_csv)
    return UploadBatch(**dict(samples=records))


def create_batch(name: str) -> int:
    """Create batch on server, return batch id"""
    data = {"name": name, "telemetry_data": {}}
    response = httpx.post(
        "https://dev.portal.gpas.world/api/v1/batches",
        headers={f"Authorization": f"Bearer {get_access_token()}"},
        json=data,
    )
    if response.is_error:
        try:
            logging.error(json.dumps(response.json(), indent=4))
        finally:
            response.raise_for_status()
    return response.json()["id"]


def create_sample(
    batch_id: int,
    status: str = "Created",
    collection_date: str = "2023-08-01",
    control: bool = False,
    country: str = "GBR",
    decontamination_fraction: int = 0,
    decontamination_in: int = 2,
    decontamination_out: int = 1,
    district: str = "dstct",
    instrument_platform: str = "illumina",
    pe_reads: dict = {},
    primer_schema: str = "",
    region: str = "region",
    specimen: str = "mycobacteria",
    checksum: str = "0123456789abcdef",
) -> int:
    """Create sample on server, return sample id"""
    data = {
        "batch_id": batch_id,
        "status": status,
        "collection_date": collection_date,
        "control": control,
        "country": country,
        "decontamination_fraction": decontamination_fraction,
        "decontamination_in": decontamination_in,
        "decontamination_out": decontamination_out,
        "district": district,
        "instrument_platform": instrument_platform,
        "pe_reads": pe_reads,
        "primer_schema": primer_schema,
        "region": region,
        "specimen": specimen,
        "checksum": checksum,
    }
    headers = {f"Authorization": f"Bearer {get_access_token()}"}
    response = httpx.post(
        "https://dev.portal.gpas.world/api/v1/samples",
        headers=headers,
        json=data,
    )
    if response.is_error:
        try:
            logging.error(json.dumps(response.json(), indent=4))
        finally:
            response.raise_for_status()
    return response.json()["id"]


def upload_sample_files(sample_id: int, reads_1: Path, reads_2: Path) -> None:
    """Upload paired FASTQ files to server"""
    reads_1, reads_2 = Path(reads_1), Path(reads_2)
    with open(reads_1, "rb") as fh:
        response1 = httpx.post(
            f"https://dev.portal.gpas.world/api/v1/samples/{sample_id}/files",
            headers={f"Authorization": f"Bearer {get_access_token()}"},
            files={"file": fh},
        )
    if response1.status_code == httpx.codes.is_error:
        try:
            logging.error(json.dumps(response1.json(), indent=4))
        finally:
            response1.raise_for_status()
    with open(reads_2, "rb") as fh:
        response2 = httpx.post(
            f"https://dev.portal.gpas.world/api/v1/samples/{sample_id}/files",
            headers={f"Authorization": f"Bearer {get_access_token()}"},
            files={"file": fh},
        )
    if response2.status_code == httpx.codes.is_error:
        try:
            logging.error(json.dumps(response2.json(), indent=4))
        finally:
            response2.raise_for_status()


def patch_sample(sample_id: int):
    """Patch sample status to Ready"""
    headers = {f"Authorization": f"Bearer {get_access_token()}"}
    response = httpx.patch(
        f"https://dev.portal.gpas.world/api/v1/samples/{sample_id}",
        headers=headers,
        json={"status": "Ready"},
    )
    if response.is_error:
        try:
            logging.error(json.dumps(response.json(), indent=4))
        finally:
            response.raise_for_status()


def make_dirty_clean_mapping(decontamination_log: list[dict]) -> dict[str, Path]:
    """Return a dictionary mapping dirty fastq filenames to clean fastq filenames"""
    d = {}
    for record in decontamination_log:
        print(record["fastq1_in_name"])
        d[record["fastq1_in_name"]] = Path(record["fastq1_out_name"])
        d[record["fastq2_in_name"]] = Path(record["fastq2_out_name"])
    return d


def upload(upload_csv: Path, dry_run: bool = False) -> None:
    """Upload a batch of one or more samples to the GPAS platform"""
    upload_csv = Path(upload_csv)
    batch = parse_upload_csv(upload_csv)
    fastq_path_tuples = [
        (upload_csv.parent / s.reads_1, upload_csv.parent / s.reads_2)
        for s in batch.samples
    ]
    decontamination_log = clean_paired_fastqs(fastqs=fastq_path_tuples, force=True)
    dirty_names_to_clean_paths = make_dirty_clean_mapping(decontamination_log)
    if not dry_run:
        batch_id = create_batch(generate_random_identifier())
        for sample in batch.samples:
            sample_id = create_sample(batch_id)
            reads_1 = dirty_names_to_clean_paths[sample.reads_1.name]
            reads_2 = dirty_names_to_clean_paths[sample.reads_2.name]
            upload_sample_files(sample_id=sample_id, reads_1=reads_1, reads_2=reads_2)
            patch_sample(sample_id)


def list_batches():
    """List batches on server"""
    headers = {f"Authorization": f"Bearer {get_access_token()}"}
    response = httpx.get(
        "https://dev.portal.gpas.world/api/v1/batches", headers=headers
    )
    if response.is_error:
        try:
            logging.error(json.dumps(response.json(), indent=4))
        finally:
            response.raise_for_status()
    return response.json()


def list_samples() -> None:
    """List samples on server"""
    headers = {f"Authorization": f"Bearer {get_access_token()}"}
    response = httpx.get(
        f"https://dev.portal.gpas.world/api/v1/samples",
        headers=headers,
    )
    if response.is_error:
        try:
            logging.error(json.dumps(response.json(), indent=4))
        finally:
            response.raise_for_status()
    return response.json()


def fetch_sample(sample_id: int):
    """Fetch sample data from server"""
    headers = {f"Authorization": f"Bearer {get_access_token()}"}
    response = httpx.get(
        f"https://dev.portal.gpas.world/api/v1/samples/{sample_id}",
        headers=headers,
    )
    if response.is_error:
        try:
            logging.error(json.dumps(response.json(), indent=4))
        finally:
            response.raise_for_status()
    return response.json()
