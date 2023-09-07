import json
import logging
from pathlib import Path

import httpx
from hostile.lib import clean_paired_fastqs

from gpas import util


logging.getLogger("httpx").setLevel(logging.WARNING)


def authenticate(
    username: str, password: str, host="https://dev.portal.gpas.world/api"
) -> None:
    """Requests, writes auth token to ~/.config/gpas/tokens/<host>"""
    host_name = util.get_host_name(host)
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.post(
            f"{host}/v1/auth/token",
            json={"username": username, "password": password},
        )
    data = response.json()
    conf_dir = Path.home() / ".config" / "gpas"
    token_dir = conf_dir / "tokens"
    token_dir.mkdir(parents=True, exist_ok=True)
    with token_dir.joinpath(f"{host_name}.json").open(mode="w") as fh:
        json.dump(data, fh)


def check_authentication(host="https://dev.portal.gpas.world/api") -> None:
    response = httpx.get(
        f"{host}/v1/batches",
        headers={"Authorization": f"Bearer {util.get_access_token()}"},
    )
    response.raise_for_status()


def create_batch(name: str) -> int:
    """Create batch on server, return batch id"""
    data = {"name": name, "telemetry_data": {}}
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.post(
            "https://dev.portal.gpas.world/api/v1/batches",
            headers={"Authorization": f"Bearer {util.get_access_token()}"},
            json=data,
        )
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
    headers = {"Authorization": f"Bearer {util.get_access_token()}"}
    logging.debug(f"Sample {data=}")
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.post(
            "https://dev.portal.gpas.world/api/v1/samples",
            headers=headers,
            json=data,
        )
    return response.json()["id"]


def trigger_run(sample_id: int):
    """Patch sample, create run, and patch run to trigger processing"""
    headers = {"Authorization": f"Bearer {util.get_access_token()}"}
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        patch_sample_response = client.patch(
            f"https://dev.portal.gpas.world/api/v1/samples/{sample_id}",
            headers=headers,
            json={"status": "Ready"},
        )
        post_run_response = client.post(
            f"https://dev.portal.gpas.world/api/v1/samples/{sample_id}/runs",
            headers=headers,
            json={"sample_id": sample_id},
        )
        run_id = post_run_response.json()["id"]
        patch_run_response = client.patch(
            f"https://dev.portal.gpas.world/api/v1/samples/{sample_id}/runs/{run_id}",
            headers=headers,
            json={"status": "Ready"},
        )


def upload(upload_csv: Path, dry_run: bool = False) -> None:
    """Upload a batch of one or more samples to the GPAS platform"""
    if not dry_run:
        check_authentication()
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
    if dry_run:
        return
    batch_name = util.generate_identifier()
    batch_id = create_batch(batch_name)
    mapping_csv_records = []

    # Create sample metadata
    for sample in batch.samples:
        name = sample.sample_name
        reads_1_clean = Path(names_logs[name]["fastq1_out_path"])
        reads_2_clean = Path(names_logs[name]["fastq2_out_path"])
        checksum = util.hash_file(reads_1_clean)
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
            checksum=checksum,
        )
        reads_1_clean_renamed = reads_1_clean.rename(
            reads_1_clean.with_name(f"{sample_id}_1.fastq.gz")
        )
        reads_2_clean_renamed = reads_2_clean.rename(
            reads_2_clean.with_name(f"{sample_id}_2.fastq.gz")
        )
        mapping_csv_records.append(
            {
                "batch_name": sample.batch_name,
                "sample_name": sample.sample_name,
                "remote_sample_name": checksum,
                "remote_batch_id": batch_id,
                "remote_sample_id": sample_id,
            }
        )
    util.write_csv(mapping_csv_records, f"{batch_name}.mapping.csv")

    # Upload reads
    for sample in batch.samples:
        util.upload_paired_fastqs(
            sample_id=sample_id,
            reads_1=reads_1_clean_renamed,
            reads_2=reads_2_clean_renamed,
        )
        logging.info(f"Uploaded {name}")
        trigger_run(sample_id)
    logging.info(f"Uploaded batch {batch_name}")


def list_batches():
    """List batches on server"""
    headers = {"Authorization": f"Bearer {util.get_access_token()}"}
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.get(
            "https://dev.portal.gpas.world/api/v1/batches", headers=headers
        )
    return response.json()


def list_samples() -> None:
    """List samples on server"""
    headers = {"Authorization": f"Bearer {util.get_access_token()}"}
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.get(
            "https://dev.portal.gpas.world/api/v1/samples",
            headers=headers,
        )
    return response.json()


def fetch_sample(sample_id: int):
    """Fetch sample data from server"""
    headers = {"Authorization": f"Bearer {util.get_access_token()}"}
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.get(
            f"https://dev.portal.gpas.world/api/v1/samples/{sample_id}",
            headers=headers,
        )
    return response.json()


def list_files(sample_id: int):
    """List output files for a sample"""
    headers = {"Authorization": f"Bearer {util.get_access_token()}"}
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.get(
            f"https://dev.portal.gpas.world/api/v1/samples/{sample_id}/latest/files",
            headers=headers,
        )
    return response.json().get("files", [])


def download(sample_id: int, filename: Path, out_dir: Path = Path(".")) -> None:
    """Download output files for a sample"""
    headers = {"Authorization": f"Bearer {util.get_access_token()}"}
    output_files = list_files(sample_id)
    with httpx.Client(timeout=600, event_hooks=util.httpx_hooks) as client:
        for item in output_files:
            run_id, _filename = item["run_id"], item["filename"]
            url = f"https://dev.portal.gpas.world/api/v1/samples/{sample_id}/runs/{run_id}/files/{filename}"
            if _filename == filename.name:
                print(True)
                download_single(
                    client=client,
                    filename=_filename,
                    url=url,
                    headers=headers,
                    out_dir=out_dir,
                )


def download_single(
    client: httpx.Client,
    filename: str,
    url: str,
    headers: dict[str, str],
    out_dir: Path,
):
    logging.info(f"Downloading {filename}")
    with httpx.stream("GET", url=url, headers=headers) as r:
        for data in r.iter_bytes():
            with Path(out_dir).joinpath(filename).open("wb") as fh:
                fh.write(data)
    logging.info(f"Downloaded {filename}")
