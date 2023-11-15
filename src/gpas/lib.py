import csv
import json
import logging
import os

from pathlib import Path

import httpx

from hostile.lib import clean_paired_fastqs
from tqdm import tqdm

import gpas

from gpas import util
from gpas.models import OutputFile


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
        check_cli_version(host)
        check_authentication(host)
    upload_csv = Path(upload_csv)
    batch = util.parse_upload_csv(upload_csv)
    logging.info(batch)

    fastq_path_tuples = [
        (upload_csv.parent / s.reads_1, upload_csv.parent / s.reads_2)
        for s in batch.samples
    ]

    decontamination_log = clean_paired_fastqs(
        fastqs=fastq_path_tuples, rename=True, force=True
    )
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
                "remote_sample_name": sample_id,
                "remote_batch_id": batch_id,
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


def fetch_output_files(
    sample_id: str, host: str, latest: bool = True
) -> dict[str, OutputFile]:
    """Return OutputFile instances for a sample, optionally including only latest run"""
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.get(
            f"{get_protocol()}://{host}/api/v1/samples/{sample_id}/latest/files",
            headers=headers,
        )
    data = response.json().get("files", [])
    output_files = {
        d["filename"]: OutputFile(
            filename=d["filename"], sample_id=d["sample_id"], run_id=d["run_id"]
        )
        for d in data
    }
    logging.debug(f"{output_files=}")
    if latest:
        max_run_id = max(output_file.run_id for output_file in output_files.values())
        output_files = {k: v for k, v in output_files.items() if v.run_id == max_run_id}
    return output_files


def parse_csv(path: Path):
    with open(path, "r") as fh:
        reader = csv.DictReader(fh)
        return [row for row in reader]


def check_cli_version(host: str) -> None:
    """Check that CLI version exceeds the server version"""
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.get(
            f"{get_protocol()}://{host}/cli-version",
        )
    server_version = response.json()["version"]
    if server_version > gpas.__version__:
        logging.warning(f"A newer version of the CLI is available, please update")


def download(
    samples: str | None = None,
    mapping_csv: Path | None = None,
    filenames: str = "main_report.json",
    out_dir: Path = Path("."),
    host: str = DEFAULT_HOST,
    debug: bool = False,
) -> None:
    """Download latest output files for a sample"""
    check_cli_version(host)
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    if mapping_csv:
        csv_records = parse_csv(Path(mapping_csv))
        guids_samples = {s["remote_sample_name"]: s["sample_name"] for s in csv_records}
        logging.info(f"Using samples {list(guids_samples.values())}")
        logging.debug(guids_samples)
    elif samples:
        guids = util.parse_comma_separated_string(samples)
        guids_samples = {guid: None for guid in guids}
        logging.info(f"Using guids {guids}")
    else:
        raise RuntimeError("Specify either a list of samples or a mapping CSV")
    filenames = util.parse_comma_separated_string(filenames)
    for guid, sample in guids_samples.items():
        output_files = fetch_output_files(sample_id=guid, host=host, latest=True)
        with httpx.Client(
            timeout=3600,  # 1 hour
            event_hooks=util.httpx_hooks,
            transport=httpx.HTTPTransport(retries=4),
        ) as client:
            for filename in filenames:
                if filename in output_files:
                    output_file = output_files[filename]
                    url = (
                        f"{get_protocol()}://{host}/api/v1/"
                        f"samples/{output_file.sample_id}/"
                        f"runs/{output_file.run_id}/"
                        f"files/{output_file.filename}"
                    )
                    download_single(
                        client=client,
                        filename=output_file.filename,
                        prefix=sample if mapping_csv else guid,
                        url=url,
                        headers=headers,
                        out_dir=Path(out_dir),
                    )
                else:
                    logging.warning(f"Skipped {filename}" f" ({guid})")


def download_single(
    client: httpx.Client,
    url: str,
    filename: str,
    prefix: str,
    headers: dict[str, str],
    out_dir: Path,
):
    logging.info(f"Downloading {filename} ({prefix})")
    with client.stream("GET", url=url, headers=headers) as r:
        file_size = int(r.headers.get("content-length", 0))
        progress = tqdm(
            total=file_size, unit="B", unit_scale=True, desc=filename, leave=False
        )
        chunk_size = 65_536
        with Path(out_dir).joinpath(f"{prefix}.{filename}").open("wb") as fh, tqdm(
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
    logging.debug(f"Downloaded {filename}")
