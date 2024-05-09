import csv
import json
import logging
import os

from pathlib import Path

import httpx

from tenacity import retry, wait_random_exponential, stop_after_attempt

from hostile.lib import ALIGNER, clean_fastqs, clean_paired_fastqs
from hostile.util import BUCKET_URL, CACHE_DIR

from packaging.version import Version
from pydantic import BaseModel
from tqdm import tqdm

import gpas
import hostile

from gpas import util, models
from gpas.util import MissingError


logging.getLogger("httpx").setLevel(logging.WARNING)

DEFAULT_HOST = "research.portal.gpas.world"
DEFAULT_PROTOCOL = "https"
HOSTILE_INDEX_NAME = "human-t2t-hla-argos985-mycob140"


class InvalidPathError(Exception):
    """Custom exception for giving nice user errors around missing paths."""

    def __init__(self, message: str):
        """Constructor, used to pass a custom message to user.

        Args:
            message (str): Message about this path
        """
        self.message = message
        super().__init__(self.message)


def get_host(cli_host: str | None) -> str:
    """Return hostname using 1) CLI argument, 2) environment variable, 3) default value"""
    if cli_host:
        return cli_host
    elif "GPAS_HOST" in os.environ:
        env_host = os.environ["GPAS_HOST"]
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
    with httpx.Client(event_hooks=util.httpx_hooks):
        response = httpx.get(
            f"{get_protocol()}://{host}/api/v1/batches",
            headers={"Authorization": f"Bearer {util.get_access_token(host)}"},
        )
    if response.is_error:
        logging.error(f"Authentication failed for host {host}")
        raise RuntimeError("Authentication failed. You may need to re-authenticate")


def create_batch(host: str) -> tuple[str, str]:
    """Create batch on server, return batch id"""
    telemetry_data = {
        "client": {
            "name": "gpas-client",
            "version": gpas.__version__,
        },
        "decontamination": {
            "name": "hostile",
            "version": hostile.__version__,
        },
    }
    data = {"telemetry_data": telemetry_data}
    with httpx.Client(
        event_hooks=util.httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
        timeout=60,
    ) as client:
        response = client.post(
            f"{get_protocol()}://{host}/api/v1/batches",
            headers={"Authorization": f"Bearer {util.get_access_token(host)}"},
            json=data,
        )
    return response.json()["id"], response.json()["name"]


@retry(wait=wait_random_exponential(multiplier=2, max=60), stop=stop_after_attempt(10))
def create_sample(
    host: str,
    batch_id: str,
    collection_date: str,
    control: bool | None,
    country: str,
    subdivision: str,
    district: str,
    client_decontamination_reads_removed_proportion: float,
    client_decontamination_reads_in: int,
    client_decontamination_reads_out: int,
    checksum: str,
    instrument_platform: util.PLATFORMS,
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
    with httpx.Client(
        event_hooks=util.httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
        timeout=60,
    ) as client:
        response = client.post(
            f"{get_protocol()}://{host}/api/v1/samples",
            headers=headers,
            json=data,
        )
    return response.json()["id"]


@retry(wait=wait_random_exponential(multiplier=2, max=60), stop=stop_after_attempt(10))
def run_sample(sample_id: str, host: str) -> str:
    """Patch sample status, create run, and patch run status to trigger processing"""
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    with httpx.Client(
        event_hooks=util.httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
        timeout=30,
    ) as client:
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


def validate_batch(
    batch: models.UploadBatch,
    host: str,
) -> None:
    """Perform pre-submission validation of a batch of sample model subsets"""
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
        event_hooks=util.httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
        timeout=60,
    ) as client:
        response = client.post(
            f"{get_protocol()}://{host}/api/v1/batches/validate",
            headers=headers,
            json=data,
        )
    logging.debug(f"{response.json()=}")


def validate(upload_csv: Path, host: str = DEFAULT_HOST) -> None:
    """Validate a given upload CSV and exit.

    Args:
        upload_csv (Path): Path to the upload CSV
        host (str, optional): Name of the host to validate against. Defaults to DEFAULT_HOST.
    """
    logging.info(f"GPAS client version {gpas.__version__} ({host})")
    logging.debug("validate()")
    upload_csv = Path(upload_csv)
    batch = models.parse_upload_csv(upload_csv)
    validate_batch(batch=batch, host=host)
    logging.info(f"Successfully validated {upload_csv}!")


def upload(
    upload_csv: Path,
    save: bool = False,
    threads: int | None = None,
    host: str = DEFAULT_HOST,
    dry_run: bool = False,
) -> None:
    """Upload a batch of one or more samples to the GPAS platform"""
    logging.info(f"GPAS client version {gpas.__version__} ({host})")
    logging.debug(f"upload() {threads=}")
    upload_csv = Path(upload_csv)
    batch = models.parse_upload_csv(upload_csv)
    if not dry_run:
        check_client_version(host)
        check_authentication(host)
        validate_batch(batch=batch, host=host)
    instrument_platform = batch.samples[0].instrument_platform
    logging.debug(f"{instrument_platform=}")
    if instrument_platform == "ont":
        upload_single(
            upload_csv=upload_csv,
            batch=batch,
            save=save,
            threads=threads,
            host=host,
            dry_run=dry_run,
        )
    elif instrument_platform == "illumina":
        upload_paired(
            upload_csv=upload_csv,
            batch=batch,
            save=save,
            threads=threads,
            host=host,
            dry_run=dry_run,
        )


def upload_single(
    upload_csv: Path,
    batch: BaseModel,
    save: bool,
    threads: int | None,
    host: str,
    dry_run: bool,
):
    fastq_paths = [upload_csv.parent / s.reads_1 for s in batch.samples]
    if threads:
        decontamination_log = clean_fastqs(
            fastqs=fastq_paths,
            index=HOSTILE_INDEX_NAME,
            rename=True,
            threads=threads,
            force=True,
        )
    else:
        decontamination_log = clean_fastqs(
            fastqs=fastq_paths,
            index=HOSTILE_INDEX_NAME,
            rename=True,
            force=True,
        )
    names_logs = dict(zip([s.sample_name for s in batch.samples], decontamination_log))
    logging.debug(f"{names_logs=}")
    if dry_run:
        return

    # Generate and submit metadata
    batch_id, batch_name = create_batch(host=host)
    mapping_csv_records = []
    upload_meta = []
    for sample in batch.samples:
        name = sample.sample_name
        reads_clean = Path(names_logs[name]["fastq1_out_path"])
        reads_dirty = Path(names_logs[name]["fastq1_in_path"])
        checksum = util.hash_file(reads_clean)
        dirty_checksum = util.hash_file(reads_dirty)
        sample_id = create_sample(
            host=host,
            batch_id=batch_id,
            collection_date=str(sample.collection_date),
            control=util.map_control_value(sample.control),
            country=sample.country,
            subdivision=sample.subdivision,
            district=sample.district,
            client_decontamination_reads_removed_proportion=names_logs[name][
                "reads_removed_proportion"
            ],
            client_decontamination_reads_in=names_logs[name]["reads_in"],
            client_decontamination_reads_out=names_logs[name]["reads_out"],
            checksum=checksum,
            instrument_platform=sample.instrument_platform,
        )
        logging.debug(f"{sample_id=}")
        reads_clean_renamed = reads_clean.rename(
            reads_clean.with_name(f"{sample_id}.clean.fastq.gz")
        )
        upload_meta.append((name, sample_id, reads_clean_renamed, dirty_checksum))
        mapping_csv_records.append(
            {
                "batch_name": sample.batch_name,
                "sample_name": sample.sample_name,
                "remote_sample_name": sample_id,
                "remote_batch_name": batch_name,
                "remote_batch_id": batch_id,
            }
        )
    util.write_csv(mapping_csv_records, f"{batch_name}.mapping.csv")

    # Upload reads
    for name, sample_id, reads_clean_renamed, dirty_checksum in upload_meta:
        util.upload_fastq(
            sample_id=sample_id,
            sample_name=name,
            reads=reads_clean_renamed,
            host=host,
            protocol=get_protocol(),
            dirty_checksum=dirty_checksum,
        )
        run_sample(sample_id=sample_id, host=host)
        if not save:
            try:
                reads_clean_renamed.unlink()
            except Exception:
                pass  # A failure here doesn't matter since upload is complete
    logging.info(f"Upload complete. Created {batch_name}.mapping.csv (keep this safe)")


def upload_paired(
    upload_csv: Path,
    batch: BaseModel,
    save: bool,
    threads: int | None,
    host: str,
    dry_run: bool,
):
    fastq_path_tuples = [
        (upload_csv.parent / s.reads_1, upload_csv.parent / s.reads_2)
        for s in batch.samples
    ]
    if threads:
        decontamination_log = clean_paired_fastqs(
            fastqs=fastq_path_tuples,
            index=HOSTILE_INDEX_NAME,
            rename=True,
            reorder=True,
            threads=threads,
            force=True,
        )
    else:
        decontamination_log = clean_paired_fastqs(
            fastqs=fastq_path_tuples,
            index=HOSTILE_INDEX_NAME,
            rename=True,
            reorder=True,
            force=True,
        )
    names_logs = dict(zip([s.sample_name for s in batch.samples], decontamination_log))
    logging.debug(f"{names_logs=}")
    if dry_run:
        return

    # Generate and submit metadata
    batch_id, batch_name = create_batch(host=host)
    mapping_csv_records = []
    upload_meta = []
    for sample in batch.samples:
        name = sample.sample_name
        reads_1_clean = Path(names_logs[name]["fastq1_out_path"])
        reads_2_clean = Path(names_logs[name]["fastq2_out_path"])
        reads_1_dirty = Path(names_logs[name]["fastq1_in_path"])
        reads_2_dirty = Path(names_logs[name]["fastq2_in_path"])
        dirty_checksum_1 = util.hash_file(reads_1_dirty)
        dirty_checksum_2 = util.hash_file(reads_2_dirty)
        checksum = util.hash_file(reads_1_clean)
        sample_id = create_sample(
            host=host,
            batch_id=batch_id,
            collection_date=str(sample.collection_date),
            control=util.map_control_value(sample.control),
            country=sample.country,
            subdivision=sample.subdivision,
            district=sample.district,
            client_decontamination_reads_removed_proportion=names_logs[name][
                "reads_removed_proportion"
            ],
            client_decontamination_reads_in=names_logs[name]["reads_in"],
            client_decontamination_reads_out=names_logs[name]["reads_out"],
            checksum=checksum,
            instrument_platform=sample.instrument_platform,
        )
        logging.debug(f"{sample_id=}")
        reads_1_clean_renamed = reads_1_clean.rename(
            reads_1_clean.with_name(f"{sample_id}_1.fastq.gz")
        )
        reads_2_clean_renamed = reads_2_clean.rename(
            reads_2_clean.with_name(f"{sample_id}_2.fastq.gz")
        )
        upload_meta.append(
            (
                name,
                sample_id,
                reads_1_clean_renamed,
                reads_2_clean_renamed,
                dirty_checksum_1,
                dirty_checksum_2,
            )
        )
        mapping_csv_records.append(
            {
                "batch_name": sample.batch_name,
                "sample_name": sample.sample_name,
                "remote_sample_name": sample_id,
                "remote_batch_name": batch_name,
                "remote_batch_id": batch_id,
            }
        )
    util.write_csv(mapping_csv_records, f"{batch_name}.mapping.csv")

    # Upload reads
    for (
        name,
        sample_id,
        reads_1_clean_renamed,
        reads_2_clean_renamed,
        dirty_checksum_1,
        dirty_checksum_2,
    ) in upload_meta:
        util.upload_paired_fastqs(
            sample_id=sample_id,
            sample_name=name,
            reads_1=reads_1_clean_renamed,
            reads_2=reads_2_clean_renamed,
            host=host,
            protocol=get_protocol(),
            dirty_checksum_1=dirty_checksum_1,
            dirty_checksum_2=dirty_checksum_2,
        )
        run_sample(sample_id=sample_id, host=host)
        if not save:
            try:
                reads_1_clean_renamed.unlink()
                reads_2_clean_renamed.unlink()
            except Exception:
                pass  # A failure here doesn't matter since upload is complete
    logging.info(f"Upload complete. Created {batch_name}.mapping.csv (keep this safe)")


def fetch_sample(sample_id: str, host: str) -> dict:
    """Fetch sample data from server"""
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    with httpx.Client(
        event_hooks=util.httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
    ) as client:
        response = client.get(
            f"{get_protocol()}://{host}/api/v1/samples/{sample_id}",
            headers=headers,
        )
    return response.json()


def query(
    samples: str | None = None,
    mapping_csv: Path | None = None,
    host: str = DEFAULT_HOST,
) -> dict[str, dict]:
    """Query sample metadata returning a dict of metadata keyed by sample ID"""
    logging.info(f"GPAS client version {gpas.__version__} ({host})")
    check_client_version(host)
    if samples:
        guids = util.parse_comma_separated_string(samples)
        guids_samples = {guid: None for guid in guids}
        logging.info(f"Using guids {guids}")
    elif mapping_csv:
        csv_records = parse_csv(Path(mapping_csv))
        guids_samples = {s["remote_sample_name"]: s["sample_name"] for s in csv_records}
        logging.info(f"Using samples in {mapping_csv}")
        logging.debug(f"{guids_samples=}")
    else:
        raise RuntimeError("Specify either a list of sample IDs or a mapping CSV")
    samples_metadata = {}
    for guid, sample in tqdm(
        guids_samples.items(), desc="Querying samples", leave=False
    ):
        name = sample if mapping_csv else guid
        samples_metadata[name] = fetch_sample(sample_id=guid, host=host)
    return samples_metadata


def status(
    samples: str | None = None,
    mapping_csv: Path | None = None,
    host: str = DEFAULT_HOST,
) -> dict[str, str]:
    """Query sample status"""
    logging.info(f"GPAS client version {gpas.__version__} ({host})")
    check_client_version(host)
    if samples:
        guids = util.parse_comma_separated_string(samples)
        guids_samples = {guid: None for guid in guids}
        logging.info(f"Using guids {guids}")
    elif mapping_csv:
        csv_records = parse_csv(Path(mapping_csv))
        guids_samples = {s["remote_sample_name"]: s["sample_name"] for s in csv_records}
        logging.info(f"Using samples in {mapping_csv}")
        logging.debug(guids_samples)
    else:
        raise RuntimeError("Specify either a list of sample IDs or a mapping CSV")
    samples_status = {}
    for guid, sample in tqdm(
        guids_samples.items(), desc="Querying samples", leave=False
    ):
        name = sample if mapping_csv else guid
        samples_status[name] = fetch_sample(sample_id=guid, host=host).get("status")
    return samples_status


def fetch_latest_input_files(sample_id: str, host: str) -> dict[str, models.RemoteFile]:
    """Return models.RemoteFile instances for a sample input files"""
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    with httpx.Client(
        event_hooks=util.httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
    ) as client:
        response = client.get(
            f"{get_protocol()}://{host}/api/v1/samples/{sample_id}/latest/input-files",
            headers=headers,
        )
    data = response.json().get("files", [])
    output_files = {
        d["filename"]: models.RemoteFile(
            filename=d["filename"],
            sample_id=d["sample_id"],
            run_id=d["run_id"],
        )
        for d in data
    }
    logging.debug(f"{output_files=}")
    return output_files


def fetch_output_files(
    sample_id: str, host: str, latest: bool = True
) -> dict[str, models.RemoteFile]:
    """Return models.RemoteFile instances for a sample, optionally including only latest run"""
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    with httpx.Client(
        event_hooks=util.httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
    ) as client:
        response = client.get(
            f"{get_protocol()}://{host}/api/v1/samples/{sample_id}/latest/files",
            headers=headers,
        )
    data = response.json().get("files", [])
    output_files = {
        d["filename"]: models.RemoteFile(
            filename=d["filename"].replace("_", ".", 1),
            sample_id=d["sample_id"],
            run_id=d["run_id"],
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


def check_client_version(host: str) -> None:
    """Raise exception if the client is outdated"""
    with httpx.Client(
        event_hooks=util.httpx_hooks,
        transport=httpx.HTTPTransport(retries=2),
        timeout=10,
    ) as client:
        response = client.get(
            f"{get_protocol()}://{host}/cli-version",
        )
    server_version = response.json()["version"]
    logging.debug(
        f"Client version {gpas.__version__}, server version: {server_version})"
    )
    if Version(server_version) > Version(gpas.__version__):
        raise util.UnsupportedClientException(gpas.__version__, server_version)


def download(
    samples: str | None = None,
    mapping_csv: Path | None = None,
    filenames: str = "main_report.json",
    inputs: bool = False,
    out_dir: Path = Path("."),
    rename: bool = True,
    host: str = DEFAULT_HOST,
) -> None:
    """Download latest output files for a sample"""
    logging.info(f"GPAS client version {gpas.__version__} ({host})")
    check_client_version(host)
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    if mapping_csv:
        csv_records = parse_csv(Path(mapping_csv))
        guids_samples = {s["remote_sample_name"]: s["sample_name"] for s in csv_records}
        logging.info(f"Using samples in {mapping_csv}")
        logging.debug(guids_samples)
    elif samples:
        guids = util.parse_comma_separated_string(samples)
        guids_samples = {guid: None for guid in guids}
        logging.info(f"Using guids {guids}")
    else:
        raise RuntimeError("Specify either a list of samples or a mapping CSV")
    filenames = util.parse_comma_separated_string(filenames)
    for guid, sample in guids_samples.items():
        try:
            output_files = fetch_output_files(sample_id=guid, host=host, latest=True)
        except MissingError:
            output_files = [] # There are no output files. The run may have failed.
        with httpx.Client(
            event_hooks=util.httpx_hooks,
            transport=httpx.HTTPTransport(retries=5),
            timeout=7200,  # 2 hours
        ) as client:
            for filename in filenames:
                prefixed_filename = f"{guid}_{filename}"
                if prefixed_filename in output_files:
                    output_file = output_files[prefixed_filename]
                    url = (
                        f"{get_protocol()}://{host}/api/v1/"
                        f"samples/{output_file.sample_id}/"
                        f"runs/{output_file.run_id}/"
                        f"files/{prefixed_filename}"
                    )
                    if rename and mapping_csv:
                        filename_fmt = f"{sample}.{prefixed_filename.partition('_')[2]}"
                    else:
                        filename_fmt = output_file.filename
                    download_single(
                        client=client,
                        filename=filename_fmt,
                        url=url,
                        headers=headers,
                        out_dir=Path(out_dir),
                    )
                elif set(
                    filter(None, filenames)
                ):  # Skip case where filenames = set("")
                    logging.warning(
                        f"Skipped {sample if sample and rename else guid}.{filename}"
                    )
            if inputs:
                input_files = fetch_latest_input_files(sample_id=guid, host=host)
                for input_file in input_files.values():
                    if rename and mapping_csv:
                        suffix = input_file.filename.partition(".")[2]
                        filename_fmt = f"{sample}.{suffix}"
                    else:
                        filename_fmt = input_file.filename
                    url = (
                        f"{get_protocol()}://{host}/api/v1/"
                        f"samples/{input_file.sample_id}/"
                        f"runs/{input_file.run_id}/"
                        f"input-files/{input_file.filename}"
                    )
                    download_single(
                        client=client,
                        filename=filename_fmt,
                        url=url,
                        headers=headers,
                        out_dir=Path(out_dir),
                    )


@retry(wait=wait_random_exponential(multiplier=2, max=60), stop=stop_after_attempt(10))
def download_single(
    client: httpx.Client,
    url: str,
    filename: str,
    headers: dict[str, str],
    out_dir: Path,
):
    logging.info(f"Downloading {filename}")
    check_outdir(out_dir)
    with client.stream("GET", url=url, headers=headers) as r:
        file_size = int(r.headers.get("content-length", 0))
        progress = tqdm(
            total=file_size, unit="B", unit_scale=True, desc=filename, leave=False
        )
        chunk_size = 262_144
        with (
            Path(out_dir).joinpath(f"{filename}").open("wb") as fh,
            tqdm(
                total=file_size,
                unit="B",
                unit_scale=True,
                desc=filename,
                leave=False,  # Works only if using a context manager
                position=0,  # Avoids leaving line break with leave=False
            ) as progress,
        ):
            for data in r.iter_bytes(chunk_size):
                fh.write(data)
                progress.update(len(data))
    logging.debug(f"Downloaded {filename}")


def download_index(name: str = HOSTILE_INDEX_NAME) -> None:
    logging.info(f"Cache directory: {CACHE_DIR}")
    logging.info(f"Manifest URL: {BUCKET_URL}/manifest.json")
    ALIGNER.minimap2.value.check_index(name)
    ALIGNER.bowtie2.value.check_index(name)


def check_outdir(path: Path) -> None:
    """Given an outdir path, check that it exists (and is a directory).

    Args:
        path (Path): Outdir path
    """
    if path.exists():
        if path.is_dir():
            return
        logging.error(f"Given out dir ({str(path)}) exists, but is a file!")
        raise InvalidPathError(f"Given out dir ({str(path)}) exists, but is a file!")

    logging.error(f"Given out dir ({str(path)}) does not exist!")
    raise InvalidPathError(f"Given out dir ({str(path)}) does not exist!")
