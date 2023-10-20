import json
import logging
import os

from pathlib import Path

import httpx

from hostile.lib import clean_paired_fastqs
from tqdm import tqdm

import gpas
from gpas import util


logging.getLogger("httpx").setLevel(logging.WARNING)
logging.info(f"gpas-client version {gpas.__version__}")


DEFAULT_HOST = "dev.portal.gpas.world"
DEFAULT_PROTOCOL = "https"


def get_host(cli_host: str | None) -> str:
    """Return hostname using 1) CLI argument, 2) environment variable, 3) default value"""
    if cli_host:
        logging.info(f"Using host {cli_host}")
        return cli_host
    elif "GPAS_HOST" in os.environ:
        env_host = os.environ["GPAS_HOST"]
        logging.info(f"Using host {env_host}")
        return env_host
    else:
        return DEFAULT_HOST


def get_protocol() -> str:
    if "GPAS_PROTOCOL" in os.environ:
        protocol = os.environ["GPAS_PROTOCOL"]
        return protocol
    else:
        return DEFAULT_PROTOCOL


def authenticate(username: str, password: str, host: str = DEFAULT_HOST) -> None:
    """Requests, writes auth token to ~/.config/gpas/tokens/<host>"""
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.post(
            f"{get_protocol()}://{host}/api/v1/auth/token",
            json={"username": username, "password": password},
        )
    data = response.json()
    conf_dir = Path.home() / ".config" / "gpas"
    token_dir = conf_dir / "tokens"
    token_dir.mkdir(parents=True, exist_ok=True)
    token_path = token_dir / f"{host}.json"
    with token_path.open(mode="w") as fh:
        json.dump(data, fh)
    logging.info(f"Authenticated ({token_path})")


def check_authentication(host: str) -> None:
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = httpx.get(
            f"{get_protocol()}://{host}/api/v1/batches",
            headers={"Authorization": f"Bearer {util.get_access_token(host)}"},
        )


def create_batch(name: str, host: str) -> int:
    """Create batch on server, return batch id"""
    data = {"name": name, "telemetry_data": {}}
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.post(
            f"{get_protocol()}://{host}/api/v1/batches",
            headers={"Authorization": f"Bearer {util.get_access_token(host)}"},
            json=data,
        )
    return response.json()["id"]


def create_sample(
    host: str,
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
) -> str:
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
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    logging.debug(f"Sample {data=}")
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.post(
            f"{get_protocol()}://{host}/api/v1/samples",
            headers=headers,
            json=data,
        )
    return response.json()["id"]


def run_sample(sample_id: str, host: str) -> int:
    """Patch sample status, create run, and patch run status to trigger processing"""
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        client.patch(
            f"{get_protocol()}://{host}/api/v1/samples/{sample_id}",
            headers=headers,
            json={"status": "Ready"},
        )
        post_run_response = client.post(
            f"{get_protocol()}://{host}/api/v1/samples/{sample_id}/runs",
            headers=headers,
            json={"sample_id": sample_id},
        )
        run_id = post_run_response.json()["id"]
        client.patch(
            f"{get_protocol()}://{host}/api/v1/samples/{sample_id}/runs/{run_id}",
            headers=headers,
            json={"status": "Ready"},
        )
        logging.debug(f"{run_id=}")
        return run_id


def upload(upload_csv: Path, host: str = DEFAULT_HOST, dry_run: bool = False) -> None:
    """Upload a batch of one or more samples to the GPAS platform"""
    if not dry_run:
        check_authentication(host)
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
    batch_id = create_batch(name=batch_name, host=host)
    mapping_csv_records = []

    # Create sample metadata
    upload_meta = []
    for sample in batch.samples:
        name = sample.sample_name
        reads_1_clean = Path(names_logs[name]["fastq1_out_path"])
        reads_2_clean = Path(names_logs[name]["fastq2_out_path"])
        checksum = util.hash_file(reads_1_clean)
        sample_id = create_sample(
            host=host,
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
        logging.debug(f"{sample_id=}")
        reads_1_clean_renamed = reads_1_clean.rename(
            reads_1_clean.with_name(f"{sample_id}_1.fastq.gz")
        )
        reads_2_clean_renamed = reads_2_clean.rename(
            reads_2_clean.with_name(f"{sample_id}_2.fastq.gz")
        )
        upload_meta.append(
            (name, sample_id, reads_1_clean_renamed, reads_2_clean_renamed)
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
    for sample in upload_meta:
        name = sample[0]
        sample_id = sample[1]
        reads_1_clean_renamed = sample[2]
        reads_2_clean_renamed = sample[3]
        util.upload_paired_fastqs(
            sample_id=sample_id,
            sample_name=name,
            reads_1=reads_1_clean_renamed,
            reads_2=reads_2_clean_renamed,
            host=host,
            protocol=get_protocol(),
        )
        run_sample(sample_id=sample_id, host=host)
    logging.info(f"Uploaded batch {batch_name}")


def list_batches(host: str, limit: int = 1000):
    """List batches on server"""
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.get(
            f"{get_protocol()}://{host}/api/v1/batches?limit={limit}", headers=headers
        )
    return response.json()


def list_samples(batch: str, host: str, limit: int = 1000) -> None:
    """List samples on server"""
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.get(
            f"{get_protocol()}://{host}/api/v1/samples?batch={batch}&limit={limit}",
            headers=headers,
        )
    return response.json()


def fetch_sample(sample_id: str, host: str):
    """Fetch sample data from server"""
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.get(
            f"{get_protocol()}://{host}/api/v1/samples/{sample_id}",
            headers=headers,
        )
    return response.json()


def list_files(sample_id: str, host: str):
    """List output files for a sample"""
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.get(
            f"{get_protocol()}://{host}/api/v1/samples/{sample_id}/latest/files",
            headers=headers,
        )
    return response.json().get("files", [])


def download(
    sample_id: str, filename: Path, out_dir: Path = Path("."), host: str = DEFAULT_HOST
) -> None:
    """Download output files for a sample"""
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    output_files = list_files(sample_id=sample_id, host=host)
    logging.info(f"{output_files=}")
    with httpx.Client(
        timeout=3600,  # 1 hour
        event_hooks=util.httpx_hooks,
        transport=httpx.HTTPTransport(retries=4),
    ) as client:
        for item in output_files:
            run_id, _filename = item["run_id"], item["filename"]
            url = f"{get_protocol()}://{host}/api/v1/samples/{sample_id}/runs/{run_id}/files/{filename}"
            if _filename == filename.name:
                download_single(
                    client=client,
                    filename=_filename,
                    url=url,
                    headers=headers,
                    out_dir=out_dir,
                )


def download_single(
    client: httpx.Client,
    url: str,
    filename: str,
    headers: dict[str, str],
    out_dir: Path,
):
    logging.info(f"Downloading {filename}")
    with client.stream("GET", url=url, headers=headers) as r:
        file_size = int(r.headers.get("content-length", 0))
        progress = tqdm(
            total=file_size, unit="B", unit_scale=True, desc=filename, leave=False
        )
        chunk_size = 65_536
        with Path(out_dir).joinpath(filename).open("wb") as fh, tqdm(
            total=file_size,
            unit="B",
            unit_scale=True,
            desc=filename,
            leave=False,  # Works only if using a context manager
            position=0,  # Avoids leaving line break with leave=False
        ) as progress:
            for data in r.iter_bytes(chunk_size):
                fh.write(data)
                progress.update(len(data))
    logging.info(f"Downloaded {filename}")
