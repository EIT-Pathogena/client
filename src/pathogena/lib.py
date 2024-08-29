import csv
import json
import logging
import os
import multiprocessing
import shutil
from getpass import getpass
from datetime import datetime, timedelta

from pathlib import Path

import httpx

from tenacity import retry, wait_random_exponential, stop_after_attempt

from hostile.lib import ALIGNER, clean_fastqs, clean_paired_fastqs
from hostile.util import BUCKET_URL, CACHE_DIR, choose_default_thread_count

from packaging.version import Version
from tqdm import tqdm

import pathogena
import hostile

from pathogena import util, models
from pathogena.models import UploadBatch, UploadSample
from pathogena.util import get_access_token, MissingError, get_token_path

logging.getLogger("httpx").setLevel(logging.WARNING)

CPU_COUNT = multiprocessing.cpu_count()
DEFAULT_HOST = "portal.eit-pathogena.com"
DEFAULT_PROTOCOL = "https"
DEFAULT_METADATA = {
    "country": None,
    "district": "",
    "subdivision": "",
    "instrument_platform": "illumina",
    "pipeline": "mycobacteria",
    "ont_read_suffix": ".fastq.gz",
    "illumina_read1_suffix": "_1.fastq.gz",
    "illumina_read2_suffix": "_2.fastq.gz",
    "max_batch_size": 50,
}
HOSTILE_INDEX_NAME = "human-t2t-hla-argos985-mycob140"


def get_host(cli_host: str | None) -> str:
    """Return hostname using 1) CLI argument, 2) environment variable, 3) default value"""
    return (
        cli_host
        if cli_host is not None
        else os.environ.get("PATHOGENA_HOST", DEFAULT_HOST)
    )


def get_protocol() -> str:
    if "PATHOGENA_PROTOCOL" in os.environ:
        protocol = os.environ["PATHOGENA_PROTOCOL"]
        return protocol
    else:
        return DEFAULT_PROTOCOL


def authenticate(host: str = DEFAULT_HOST) -> None:
    """Requests a user auth token, writes to ~/.config/pathogena/tokens/<host>.json"""
    logging.info(f"Authenticating with {host}")
    username = input("Enter your username: ")
    password = getpass(prompt="Enter your password (hidden): ")
    with httpx.Client(event_hooks=util.httpx_hooks) as client:
        response = client.post(
            f"{get_protocol()}://{host}/api/v1/auth/token",
            json={"username": username, "password": password},
        )
    data = response.json()

    token_path = get_token_path(host)

    # Convert the expiry in seconds into a readable date, default token should be 7 days.
    one_week_in_seconds = 604800
    expires_in = data.get("expires_in", one_week_in_seconds)
    expiry = datetime.now() + timedelta(seconds=expires_in)
    data["expiry"] = expiry.isoformat()

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
        raise RuntimeError(
            "Authentication failed. You may need to re-authenticate with `pathogena auth`"
        )


def get_credit_balance(host: str):
    logging.info(f"Getting credit balance for {host}")
    with httpx.Client(
        event_hooks=util.httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
        timeout=15,
    ) as client:
        response = client.get(
            f"{get_protocol()}://{host}/api/v1/credits/balance",
            headers={"Authorization": f"Bearer {get_access_token(host)}"},
        )
        if response.status_code == 200:
            logging.info(f"Your remaining account balance is {response.text} credits")
        elif response.status_code == 402:
            logging.error(
                "Your account doesn't have enough credits to fulfil the number of Samples in your Batch."
            )


def create_batch_on_server(host: str, number_of_samples: int) -> tuple[str, str]:
    """Create batch on server, return batch id, a transaction will be created at this point for the expected
    total samples in the BatchModel."""
    telemetry_data = {
        "client": {
            "name": "pathogena-client",
            "version": pathogena.__version__,
        },
        "decontamination": {
            "name": "hostile",
            "version": hostile.__version__,
        },
    }
    data = {
        "telemetry_data": telemetry_data,
        "expected_sample_count": number_of_samples,
    }
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
    sample: UploadSample,
) -> str:
    """Create sample on server, return sample id"""
    data = {
        "batch_id": batch_id,
        "status": "Created",
        "collection_date": str(sample.collection_date),
        "control": util.map_control_value(sample.control),
        "country": sample.country,
        "subdivision": sample.subdivision,
        "district": sample.district,
        "client_decontamination_reads_removed_proportion": sample.reads_removed,
        "client_decontamination_reads_in": sample.reads_in,
        "client_decontamination_reads_out": sample.reads_out,
        "checksum": sample.reads_1_pre_upload_checksum,
        "instrument_platform": sample.instrument_platform,
        "specimen_organism": sample.specimen_organism,
        "host_organism": sample.host_organism,
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


def decontaminate_samples_with_hostile(
    batch: models.UploadBatch,
    threads: int,
    output_dir: Path = Path("."),
) -> dict:
    """Run Hostile to remove human reads from a given CSV file of FastQ files and return metadata related to the batch"""
    logging.debug(f"decontaminate_samples_with_hostile() {threads=} {output_dir=}")
    logging.info(
        f"Removing human reads from {batch.instrument_platform.upper()} FastQ files and storing in {output_dir.absolute()}"
    )
    fastq_paths = []
    decontamination_metadata = {}
    if batch.is_ont():
        fastq_paths = [sample.reads_1_resolved_path for sample in batch.samples]
        decontamination_metadata = clean_fastqs(
            fastqs=fastq_paths,
            index=HOSTILE_INDEX_NAME,
            rename=True,
            reorder=True,
            threads=threads if threads else choose_default_thread_count(CPU_COUNT),
            out_dir=output_dir,
            force=True,
        )
    elif batch.is_illumina():
        for sample in batch.samples:
            fastq_paths.append(
                (sample.reads_1_resolved_path, sample.reads_2_resolved_path)
            )
        decontamination_metadata = clean_paired_fastqs(
            fastqs=fastq_paths,
            index=HOSTILE_INDEX_NAME,
            rename=True,
            reorder=True,
            threads=threads if threads else choose_default_thread_count(CPU_COUNT),
            out_dir=output_dir,
            force=True,
        )
    batch_metadata = dict(
        zip([s.sample_name for s in batch.samples], decontamination_metadata)
    )
    batch.ran_through_hostile = True
    logging.info(
        f"Human reads removed from input samples and can be found here: {output_dir.absolute()}"
    )
    return batch_metadata


def upload_batch(
    batch: models.UploadBatch,
    save: bool = False,
    host: str = DEFAULT_HOST,
):
    # Generate and submit metadata
    batch_id, batch_name = create_batch_on_server(
        host=host, number_of_samples=len(batch.samples)
    )
    mapping_csv_records = []
    upload_meta = []
    for sample in batch.samples:
        sample_id = create_sample(
            host=host,
            batch_id=batch_id,
            sample=sample,
        )
        logging.debug(f"{sample_id=}")
        sample.reads_1_upload_file = prepare_upload_files(
            target_filepath=sample.reads_1_cleaned_path
            if batch.ran_through_hostile
            else sample.reads_1_resolved_path,
            sample_id=sample_id,
            decontaminated=batch.ran_through_hostile,
            read_num=1,
        )
        if sample.is_illumina():
            sample.reads_2_upload_file = prepare_upload_files(
                target_filepath=sample.reads_2_cleaned_path
                if batch.ran_through_hostile
                else sample.reads_2_resolved_path,
                sample_id=sample_id,
                decontaminated=batch.ran_through_hostile,
                read_num=2,
            )
        upload_meta.append(
            (
                sample.sample_name,
                sample_id,
                sample.reads_1_upload_file,
                sample.reads_2_upload_file if sample.is_illumina() else None,
                sample.reads_1_dirty_checksum,
                sample.reads_2_dirty_checksum if sample.is_illumina() else None,
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
    logging.info(f"The mapping file {batch_name}.mapping.csv has been created.")
    logging.info(
        "You can monitor the progress of your batch in EIT Pathogena here: "
        f"{get_protocol()}://{host}/batches/{batch_id}"
    )

    # Upload reads
    for (
        name,
        sample_id,
        reads1_to_upload,
        reads2_to_upload,
        reads_1_dirty_checksum,
        reads_2_dirty_checksum,
    ) in upload_meta:
        util.upload_fastq(
            sample_id=sample_id,
            sample_name=name,
            reads=reads1_to_upload,
            host=host,
            protocol=get_protocol(),
            dirty_checksum=reads_1_dirty_checksum,
        )
        if batch.is_illumina():
            util.upload_fastq(
                sample_id=sample_id,
                sample_name=name,
                reads=reads2_to_upload,
                host=host,
                protocol=get_protocol(),
                dirty_checksum=reads_2_dirty_checksum,
            )
        run_sample(sample_id=sample_id, host=host)
        if not save:
            remove_file(file_path=reads1_to_upload)
            if batch.is_illumina():
                remove_file(file_path=reads2_to_upload)
    logging.info(f"Upload complete. Created {batch_name}.mapping.csv (keep this safe)")


def validate_upload_permissions(batch: UploadBatch, protocol: str, host: str) -> None:
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
            f"{protocol}://{host}/api/v1/batches/validate",
            headers=headers,
            json=data,
        )
    logging.debug(f"{response.json()=}")


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
    check_version_compatibility(host)
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
    check_version_compatibility(host)
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


def check_version_compatibility(host: str) -> None:
    """
    Check the client version expected by the server (Portal) and raise an exception if the client version is not
    compatible
    """
    with httpx.Client(
        event_hooks=util.httpx_hooks,
        transport=httpx.HTTPTransport(retries=2),
        timeout=10,
    ) as client:
        response = client.get(
            f"{get_protocol()}://{host}/cli-version",
        )
    lowest_cli_version = response.json()["version"]
    logging.debug(
        f"Client version {pathogena.__version__}, server version: {lowest_cli_version})"
    )
    if Version(pathogena.__version__) < Version(lowest_cli_version):
        raise util.UnsupportedClientException(pathogena.__version__, lowest_cli_version)


# noinspection PyBroadException
def check_for_newer_version() -> None:
    """Check whether there is a new version of the CLI available on Pypi and advise the user to upgrade."""
    try:
        pathogena_pypi_url = "https://pypi.org/pypi/pathogena/json"
        with httpx.Client(transport=httpx.HTTPTransport(retries=2)) as client:
            response = client.get(
                pathogena_pypi_url,
                headers={"Accept": "application/json"},
            )
            if response.status_code == 200:
                latest_version = Version(
                    response.json()
                    .get("info", {})
                    .get("version", pathogena.__version__)
                )
                if Version(pathogena.__version__) < latest_version:
                    logging.info(
                        f"A new version of the EIT Pathogena CLI ({latest_version}) is available to install,"
                        f" please follow the installation steps in the README.md file to upgrade."
                    )
    except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException):
        pass
    except Exception:  # Errors in this check should never prevent further CLI usage, ignore all errors.
        pass


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
    check_version_compatibility(host)
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
            output_files = []  # There are no output files. The run may have failed.
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


def prepare_upload_files(
    target_filepath: Path, sample_id: str, read_num: int, decontaminated: bool = False
) -> Path:
    """Rename the files to be compatible with what the server is expecting, which is `*_{1,2}.fastq.gz` and
    gzip the file if it isn't already, which should only be if the files haven't been run through Hostile.
    """
    new_reads_filename = f"{sample_id}_{read_num}.fastq.gz"
    if decontaminated:
        upload_filepath = target_filepath.rename(
            target_filepath.with_name(new_reads_filename)
        )
    else:
        if target_filepath.suffix != ".gz":
            upload_filepath = util.gzip_file(target_filepath, new_reads_filename)
        else:
            upload_filepath = shutil.copyfile(
                target_filepath, target_filepath.with_name(new_reads_filename)
            )
    return upload_filepath


def remove_file(file_path: Path) -> None:
    try:
        file_path.unlink()
    except OSError:
        logging.error(
            f"Failed to delete upload files created during execution, "
            f"files may still be in {file_path.parent}"
        )
    except Exception:
        pass  # A failure here doesn't matter since upload is complete
