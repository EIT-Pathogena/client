import asyncio
import json
import logging

from pathlib import Path

import httpx

from hostile.lib import clean_paired_fastqs

from gpas_client import util


def authenticate(
    username: str, password: str, host="https://dev.portal.gpas.world/api"
) -> None:
    """Requests, writes auth token to ~/.config/gpas/tokens/<host>"""
    host_name = util.get_host_name(host)
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


def create_batch(name: str) -> int:
    """Create batch on server, return batch id"""
    data = {"name": name, "telemetry_data": {}}
    response = httpx.post(
        "https://dev.portal.gpas.world/api/v1/batches",
        headers={f"Authorization": f"Bearer {util.get_access_token()}"},
        json=data,
    )
    if response.is_error:
        try:
            logging.error(json.dumps(response.json(), indent=4))
        finally:
            response.raise_for_status()
    logging.debug(f"{response.json()=}")
    return response.json()["id"]


def create_sample(
    batch_id: int,
    collection_date: str,
    control: bool | None,
    country: str,
    subdivision: str,
    district: str,
    client_decontamination_reads_removed_proportion: float,
    client_decontamination_reads_in: int,
    client_decontamination_reads_out: int,
    checksum: str,
    instrument_platform: str = "illumina",
    specimen_organism: str = "mycobacteria",
    host_organism: str = "homo sapiens",
) -> int:
    """Create sample on server, return sample id"""
    data = {
        "batch_id": batch_id,
        "status": "Created",
        "collection_date": str(collection_date),
        "control": control,
        "country": country,
        "subdivision": subdivision,
        "district": district,
        "client_decontamination_reads_removed_proportion": client_decontamination_reads_removed_proportion,
        "client_decontamination_reads_in": client_decontamination_reads_in,
        "client_decontamination_reads_out": client_decontamination_reads_out,
        "checksum": checksum,
        "instrument_platform": instrument_platform,
        "specimen_organism": specimen_organism,
        "host_organism": host_organism,
    }
    headers = {f"Authorization": f"Bearer {util.get_access_token()}"}
    logging.debug(f"Sample {data=}")
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
    logging.debug(f"{response.json()=}")
    return response.json()["id"]


def patch_sample(sample_id: int):
    """Patch sample status to Ready"""
    headers = {f"Authorization": f"Bearer {util.get_access_token()}"}
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


def upload(upload_csv: Path, dry_run: bool = False) -> None:
    """Upload a batch of one or more samples to the GPAS platform"""
    upload_csv = Path(upload_csv)
    batch = util.parse_upload_csv(upload_csv)

    fastq_path_tuples = [
        (upload_csv.parent / s.reads_1, upload_csv.parent / s.reads_2)
        for s in batch.samples
    ]

    decontamination_log = clean_paired_fastqs(fastqs=fastq_path_tuples, force=True)
    names_logs = dict(zip([s.sample_name for s in batch.samples], decontamination_log))
    logging.debug(f"{names_logs=}")
    control_map = {"positive": True, "negative": False, "": None}
    if not dry_run:
        batch_name = util.generate_identifier()
        batch_id = create_batch(batch_name)
        mapping_csv_records = []
        for sample in batch.samples:
            name = sample.sample_name
            reads_1_clean = Path(names_logs[name]["fastq1_out_path"])
            reads_2_clean = Path(names_logs[name]["fastq2_out_path"])
            sample_id = create_sample(
                batch_id=batch_id,
                collection_date=str(sample.collection_date),
                control=control_map[sample.control],
                country=sample.country,
                subdivision=sample.subdivision,
                district=sample.district,
                client_decontamination_reads_removed_proportion=names_logs[name][
                    "reads_removed_proportion"
                ],
                client_decontamination_reads_in=names_logs[name]["reads_in"],
                client_decontamination_reads_out=names_logs[name]["reads_out"],
                checksum=util.hash_file(reads_1_clean),
            )
            mapping_csv_records.append(
                {
                    "batch_name": sample.batch_name,
                    "sample_name": sample.sample_name,
                    "remote_batch_name": batch_id,
                    "remote_sample_name": sample_id,
                }
            )
            asyncio.run(
                util.upload_paired_fastqs(
                    sample_id=sample_id, reads_1=reads_1_clean, reads_2=reads_2_clean
                )
            )
            logging.info(f"Uploaded {name}")
            patch_sample(sample_id)
        util.write_csv(mapping_csv_records, f"{batch_name}.mapping.csv")
        logging.info(f"Uploaded batch {batch_name}")


def list_batches():
    """List batches on server"""
    headers = {f"Authorization": f"Bearer {util.get_access_token()}"}
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
    headers = {f"Authorization": f"Bearer {util.get_access_token()}"}
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
    headers = {f"Authorization": f"Bearer {util.get_access_token()}"}
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
