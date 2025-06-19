import csv
import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from getpass import getpass
from json import JSONDecodeError
from pathlib import Path

import hostile
import httpx
from hostile.lib import ALIGNER, clean_fastqs, clean_paired_fastqs
from hostile.util import BUCKET_URL, CACHE_DIR, choose_default_thread_count
from packaging.version import Version
from tenacity import retry, stop_after_attempt, wait_random_exponential
from tqdm import tqdm

import pathogena
from pathogena import batch_upload_apis, models, upload_utils, util
from pathogena.constants import (
    CPU_COUNT,
    DEFAULT_APP_HOST,
    DEFAULT_HOST,
    DEFAULT_PROTOCOL,
    HOSTILE_INDEX_NAME,
)
from pathogena.errors import APIError, MissingError, UnsupportedClientError
from pathogena.log_utils import httpx_hooks
from pathogena.models import UploadBatch, UploadSample
from pathogena.upload_utils import (
    PreparedFiles,
    UploadData,
    get_upload_host,
    prepare_files,
)
from pathogena.util import get_access_token, get_token_path

logging.getLogger("httpx").setLevel(logging.WARNING)


def get_host(cli_host: str | None = None) -> str:
    """Return hostname using 1) CLI argument, 2) environment variable, 3) default value.

    Args:
        cli_host (str | None): The host provided via CLI argument.

    Returns:
        str: The resolved hostname.
    """
    return (
        cli_host
        if cli_host is not None
        else os.environ.get("PATHOGENA_HOST", DEFAULT_HOST)
    )


def get_protocol() -> str:
    """Get the protocol to use for communication.

    Returns:
        str: The protocol (e.g., 'http', 'https').
    """
    if "PATHOGENA_PROTOCOL" in os.environ:
        protocol = os.environ["PATHOGENA_PROTOCOL"]
        return protocol
    else:
        return DEFAULT_PROTOCOL


def authenticate(host: str = DEFAULT_HOST) -> None:
    """Requests a user auth token, writes to ~/.config/pathogena/tokens/<host>.json.

    Args:
        host (str): The host server. Defaults to DEFAULT_HOST.
    """
    logging.info(f"Authenticating with {host}")
    username = input("Enter your username: ")
    password = getpass(prompt="Enter your password (hidden): ")
    with httpx.Client(event_hooks=httpx_hooks) as client:
        response = client.post(
            f"{get_protocol()}://{host}/api/v1/auth/token",
            json={"username": username, "password": password},
            follow_redirects=True,
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
    """Check if the user is authenticated.

    Args:
        host (str): The host server.

    Raises:
        RuntimeError: If authentication fails.
    """
    with httpx.Client(event_hooks=httpx_hooks):
        response = httpx.get(
            f"{get_protocol()}://{host}/api/v1/batches",
            headers={"Authorization": f"Bearer {util.get_access_token(host)}"},
            follow_redirects=True,
        )
    if response.is_error:
        logging.error(f"Authentication failed for host {host}")
        raise RuntimeError(
            "Authentication failed. You may need to re-authenticate with `pathogena auth`"
        )


def get_amplicon_schemes(host: str | None = None) -> list[str]:
    """Fetch valid amplicon schemes from the server.

    Returns:
        list[str]: List of valid amplicon schemes.
    """
    with httpx.Client(event_hooks=httpx_hooks):
        response = httpx.get(
            f"{get_protocol()}://{get_host(host)}/api/v1/amplicon_schemes",
        )
    if response.is_error:
        logging.error(f"Amplicon schemes could not be fetched from {get_host(host)}")
        raise RuntimeError(
            f"Amplicon schemes could not be fetched from the {get_host(host)}. Please try again later."
        )
    return [val for val in response.json()["amplicon_schemes"] if val is not None]


def get_credit_balance(host: str) -> None:
    """Get the credit balance for the user.

    Args:
        host (str): The host server.
    """
    logging.info(f"Getting credit balance for {host}")
    with httpx.Client(
        event_hooks=httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
        timeout=15,
    ) as client:
        response = client.get(
            f"{get_protocol()}://{host}/api/v1/credits/balance",
            headers={"Authorization": f"Bearer {get_access_token(host)}"},
            follow_redirects=True,
        )
        if response.status_code == 200:
            logging.info(f"Your remaining account balance is {response.text} credits")
        elif response.status_code == 402:
            logging.error(
                "Your account doesn't have enough credits to fulfil the number of Samples in your Batch."
            )


def create_batch_on_server(
    batch: UploadBatch,
    host: str,
    amplicon_scheme: str | None,
    validate_only: bool = False,
) -> tuple[str, str, str, str]:
    """Create batch on server, return batch id.

    A transaction will be created at this point for the expected
    total samples in the BatchModel.

    Args:
        host (str): The host server.
        number_of_samples (int): The expected number of samples in the batch.
        amplicon_scheme (str | None): The amplicon scheme to use.
        validate_only (bool): Whether to validate only. Defaults to False.

    Returns:
        tuple[str, str]: The batch ID and name.
    """
    # Assume every sample in batch has same collection date and country etc
    instrument_platform = batch.samples[0].instrument_platform
    collection_date = batch.samples[0].collection_date
    country = batch.samples[0].country
    telemetry_data = {
        "client": {
            "name": "pathogena-client",
            "version": pathogena.__version__,
        },
        "decontamination": {
            "name": "hostile",
            "version": hostile.__version__,
        },
        "specimen_organism": batch.samples[0].specimen_organism,
    }

    local_batch_name = (
        batch.samples[0].batch_name
        if batch.samples[0].batch_name not in ["", " ", None]
        else f"batch_{collection_date}"
    )
    data = {
        "collection_date": str(collection_date),
        "instrument": instrument_platform,
        "country": country,
        "name": local_batch_name,
        "amplicon_scheme": amplicon_scheme,
        "telemetry_data": telemetry_data,
    }

    url = f"{get_protocol()}://{host}/api/v1/batches"
    if validate_only:
        url += "/validate_creation"
    try:
        with httpx.Client(
            event_hooks=httpx_hooks,
            transport=httpx.HTTPTransport(retries=5),
            timeout=60,
            follow_redirects=True,
        ) as client:
            batch_create_response = client.post(
                f"{get_protocol()}://{get_upload_host()}/api/v1/batches/",
                headers={
                    "Authorization": f"Bearer {util.get_access_token(host)}",
                    "accept": "application/json",
                },
                json=data,
                follow_redirects=True,
            )
            if validate_only:
                # Don't attempt to return data if just validating (as there's none there)
                return None, None, None, None  # type: ignore

            created_batch = batch_create_response.json()
            batch_id = created_batch["id"]
            legacy_batch_id = created_batch["legacy_batch_id"]

    except JSONDecodeError:
        logging.error(
            f"Unable to communicate with the upload endpoint ({get_upload_host()}). Please check this has been set "
            f"correctly and try again."
        )
        exit(1)
    except httpx.HTTPError as err:
        raise APIError(
            f"Failed to fetch batch status: {batch_create_response.text}",
            batch_create_response.status_code,
        ) from err

    # now make the legacy portal request to get the legacy batch name
    try:
        with httpx.Client(
            event_hooks=httpx_hooks,
            transport=httpx.HTTPTransport(retries=5),
            timeout=60,
            follow_redirects=True,
        ) as client:
            legacy_batch_response = client.get(
                f"{get_protocol()}://{get_host()}/api/v1/batches/{legacy_batch_id}",
                headers={
                    "Authorization": f"Bearer {util.get_access_token(host)}",
                    "accept": "application/json",
                },
                follow_redirects=True,
            )
            legacy_batch = legacy_batch_response.json()

            remote_batch_name = legacy_batch["name"]
        return (batch_id, local_batch_name, remote_batch_name, legacy_batch_id)
    except JSONDecodeError:
        logging.error(
            f"Unable to communicate with the legacy endpoint ({get_host()}). Please check this has been set "
            f"correctly and try again."
        )
        exit(1)
    except httpx.HTTPError as err:
        raise APIError(
            f"Failed to fetch batch status: {legacy_batch_response.text}",
            legacy_batch_response.status_code,
        ) from err


def decontaminate_samples_with_hostile(
    batch: models.UploadBatch,
    threads: int,
    output_dir: Path = Path("."),
) -> dict:
    """Run Hostile to remove human reads from a given CSV file of FastQ files and return metadata related to the batch.

    Args:
        batch (models.UploadBatch): The batch of samples to decontaminate.
        threads (int): The number of threads to use.
        output_dir (Path): The output directory for the cleaned FastQ files.

    Returns:
        dict: Metadata related to the batch.
    """
    logging.debug(f"decontaminate_samples_with_hostile() {threads=} {output_dir=}")
    logging.info(
        f"Removing human reads from {str(batch.instrument_platform).upper()} FastQ files and storing in {output_dir.absolute()}"
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
            aligner_args=" --local",
        )
    batch_metadata = dict(
        zip(
            [s.sample_name for s in batch.samples],
            decontamination_metadata,
            strict=False,
        )
    )
    batch.ran_through_hostile = True
    logging.info(
        f"Human reads removed from input samples and can be found here: {output_dir.absolute()}"
    )
    return batch_metadata


def get_remote_sample_name(
    sample: UploadSample, prepared_files: PreparedFiles
) -> (str, str):
    """Get the remote names of the sample given the UploadSample object from the prepared files.

    Args:
        sample (UploadSample): The sample for which to find the ID.
        prepared_files (PreparedFiles): The prepared files containing resolved paths.
    """
    for file in prepared_files["files"]:
        resolved_path = file["file"]["resolved_path"]
        if (
            sample.reads_1_resolved_path == resolved_path
            or sample.reads_2_resolved_path == resolved_path
        ):
            return file["sample_id"]
    raise ValueError(
        f"Unable to determine sample ID for sample name {sample.sample_name}."
    )


def upload_batch(
    batch: models.UploadBatch,
    save: bool = False,
    host: str = DEFAULT_HOST,
    validate_only: bool = False,
) -> None:
    """Upload a batch of samples.

    Args:
        batch (models.UploadBatch): The batch of samples to upload.
        save (bool): Whether to keep the files saved.
        host (str): The host server.
        validate_only (bool): Whether we should actually upload or just validate batch.
    """
    batch_id, local_batch_name, remote_batch_name, legacy_batch_id = (
        create_batch_on_server(
            batch=batch,
            host=host,
            amplicon_scheme=batch.samples[0].amplicon_scheme,
            validate_only=validate_only,
        )
    )
    if validate_only:
        logging.info(f"Batch creation for {local_batch_name} validated successfully")
        return
    mapping_csv_records = []

    prepared_files = prepare_files(
        batch_pk=batch_id,
        samples=batch.samples,
        api_client=batch_upload_apis.UploadAPIClient(),
    )

    upload_file_type = UploadData(
        access_token=util.get_access_token(get_host(None)),
        batch_pk=batch_id,
        env=get_upload_host(),
        samples=batch.samples,
        upload_session=prepared_files["uploadSession"],
    )

    for sample in batch.samples:
        remote_sample_name = get_remote_sample_name(
            sample=sample, prepared_files=prepared_files
        )
        mapping_csv_records.append(
            {
                "batch_name": local_batch_name,
                "sample_name": sample.sample_name,
                "remote_sample_name": remote_sample_name,
                "remote_batch_name": remote_batch_name,
                "remote_batch_id": batch_id,
            }
        )
    util.write_csv(mapping_csv_records, f"{remote_batch_name}.mapping.csv")
    logging.info(f"The mapping file {remote_batch_name}.mapping.csv has been created.")
    logging.info(
        "You can monitor the progress of your batch in EIT Pathogena here: "
        f"{get_protocol()}://{os.environ.get('PATHOGENA_APP_HOST', DEFAULT_APP_HOST)}/batches/{legacy_batch_id}"
    )

    upload_utils.upload_fastq(
        upload_data=upload_file_type,
        prepared_files=prepared_files,
        api_client=batch_upload_apis.UploadAPIClient(),
    )

    if not save:
        for file in batch.samples:
            remove_file(file_path=file.reads_1_upload_file)  # type: ignore
            if batch.is_illumina():
                remove_file(file_path=file.reads_2_upload_file)  # type: ignore
    logging.info(
        f"Upload complete. Created {remote_batch_name}.mapping.csv (keep this safe)"
    )


def validate_upload_permissions(batch: UploadBatch, protocol: str, host: str) -> None:
    """Perform pre-submission validation of a batch of sample model subsets.

    Args:
        batch (UploadBatch): The batch to validate.
        protocol (str): The protocol to use.
        host (str): The host server.
    """
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
        event_hooks=httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
        timeout=60,
    ) as client:
        response = client.post(
            f"{protocol}://{host}/api/v1/batches/validate",
            headers=headers,
            json=data,
            follow_redirects=True,
        )
    logging.debug(f"{response.json()=}")


def fetch_sample(sample_id: str, host: str) -> dict:
    """Fetch sample data from the server.

    Args:
        sample_id (str): The sample ID.
        host (str): The host server.

    Returns:
        dict: The sample data.
    """
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    with httpx.Client(
        event_hooks=httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
    ) as client:
        response = client.get(
            f"{get_protocol()}://{host}/api/v1/samples/{sample_id}",
            headers=headers,
            follow_redirects=True,
        )
    return response.json()


def query(
    samples: str | None = None,
    mapping_csv: Path | None = None,
    host: str = DEFAULT_HOST,
) -> dict[str, dict]:
    """Query sample metadata returning a dict of metadata keyed by sample ID.

    Args:
        query_string (str): The query string.
        host (str): The host server.
        protocol (str): The protocol to use. Defaults to DEFAULT_PROTOCOL.

    Returns:
        dict: The query result.
    """
    check_version_compatibility(host)
    if samples:
        guids = util.parse_comma_separated_string(samples)
        guids_samples = dict.fromkeys(guids)
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
    """Get the status of samples from the server.

    Args:
        samples (str | None): A comma-separated list of sample IDs.
        mapping_csv (Path | None): The path to a CSV file containing sample mappings.
        host (str): The host server. Defaults to DEFAULT_HOST.

    Returns:
        dict[str, str]: A dictionary with sample IDs as keys and their statuses as values.
    """
    check_version_compatibility(host)
    if samples:
        guids = util.parse_comma_separated_string(samples)
        guids_samples = dict.fromkeys(guids)
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
    """Return models.RemoteFile instances for a sample input files.

    Args:
        sample_id (str): The sample ID.
        host (str): The host server.

    Returns:
        dict[str, models.RemoteFile]: The latest input files.
    """
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    with httpx.Client(
        event_hooks=httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
    ) as client:
        response = client.get(
            f"{get_protocol()}://{host}/api/v1/samples/{sample_id}/latest/input-files",
            headers=headers,
            follow_redirects=True,
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
    """Return models.RemoteFile instances for a sample, optionally including only latest run.

    Args:
        sample_id (str): The sample ID.
        host (str): The host server.
        protocol (str): The protocol to use. Defaults to DEFAULT_PROTOCOL.

    Returns:
        dict[str, models.RemoteFile]: The output files.
    """
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    with httpx.Client(
        event_hooks=httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
    ) as client:
        response = client.get(
            f"{get_protocol()}://{host}/api/v1/samples/{sample_id}/latest/files",
            headers=headers,
            follow_redirects=True,
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


def parse_csv(path: Path) -> list[dict]:
    """Parse a CSV file.

    Args:
        path (Path): The path to the CSV file.

    Returns:
        list[dict]: The parsed CSV data.
    """
    with open(path) as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def check_version_compatibility(host: str) -> None:
    """Check the client version expected by the server (Portal).

    Raise an exception if the client version is not
    compatible.

    Args:
        host (str): The host server.
    """
    with httpx.Client(
        event_hooks=httpx_hooks,
        transport=httpx.HTTPTransport(retries=2),
        timeout=10,
    ) as client:
        response = client.get(
            f"{get_protocol()}://{host}/cli-version", follow_redirects=True
        )
    lowest_cli_version = response.json()["version"]
    logging.debug(
        f"Client version {pathogena.__version__}, server version: {lowest_cli_version})"
    )
    if Version(pathogena.__version__) < Version(lowest_cli_version):
        raise UnsupportedClientError(pathogena.__version__, lowest_cli_version)


# noinspection PyBroadException
def check_for_newer_version() -> None:
    """Check whether there is a new version of the CLI available on Pypi and advise the user to upgrade."""
    try:
        pathogena_pypi_url = "https://pypi.org/pypi/pathogena/json"
        with httpx.Client(transport=httpx.HTTPTransport(retries=2)) as client:
            response = client.get(
                pathogena_pypi_url,
                headers={"Accept": "application/json"},
                follow_redirects=True,
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
    """Download the latest output files for a sample.

    Args:
        samples (str | None): A comma-separated list of sample IDs.
        mapping_csv (Path | None): The path to a CSV file containing sample mappings.
        filenames (str): A comma-separated list of filenames to download. Defaults to "main_report.json".
        inputs (bool): Whether to download input files as well. Defaults to False.
        out_dir (Path): The directory to save the downloaded files. Defaults to the current directory.
        rename (bool): Whether to rename the downloaded files based on the sample name. Defaults to True.
        host (str): The host server. Defaults to DEFAULT_HOST.
    """
    check_version_compatibility(host)
    headers = {"Authorization": f"Bearer {util.get_access_token(host)}"}
    if mapping_csv:
        csv_records = parse_csv(Path(mapping_csv))
        guids_samples = {s["remote_sample_name"]: s["sample_name"] for s in csv_records}
        logging.info(f"Using samples in {mapping_csv}")
        logging.debug(guids_samples)
    elif samples:
        guids = util.parse_comma_separated_string(samples)
        guids_samples = dict.fromkeys(guids)
        logging.info(f"Using guids {guids}")
    else:
        raise RuntimeError("Specify either a list of samples or a mapping CSV")
    unique_filenames: set[str] = util.parse_comma_separated_string(filenames)
    for guid, sample in guids_samples.items():
        try:
            output_files = fetch_output_files(sample_id=guid, host=host, latest=True)
        except MissingError:
            output_files = {}  # There are no output files. The run may have failed.
        with httpx.Client(
            event_hooks=httpx_hooks,
            transport=httpx.HTTPTransport(retries=5),
            timeout=7200,  # 2 hours
        ) as client:
            for filename in unique_filenames:
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
) -> None:
    """Download a single file from the server with retries.

    Args:
        client (httpx.Client): The HTTP client to use for the request.
        url (str): The URL of the file to download.
        filename (str): The name of the file to save.
        headers (dict[str, str]): The headers to include in the request.
        out_dir (Path): The directory to save the downloaded file.
    """
    logging.info(f"Downloading {filename}")
    with client.stream("GET", url=url, headers=headers) as r:
        file_size = int(r.headers.get("content-length", 0))
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
    """Download and cache the host decontamination index.

    Args:
        name (str): The name of the index. Defaults to HOSTILE_INDEX_NAME.
    """
    logging.info(f"Cache directory: {CACHE_DIR}")
    logging.info(f"Manifest URL: {BUCKET_URL}/manifest.json")
    ALIGNER.minimap2.value.check_index(name)
    ALIGNER.bowtie2.value.check_index(name)


def prepare_upload_files(
    target_filepath: Path, sample_id: str, read_num: int, decontaminated: bool = False
) -> Path:
    """Rename the files to be compatible with what the server is expecting.

    Which is `*_{1,2}.fastq.gz` and
    gzip the file if it isn't already,
    which should only be if the files haven't been run through Hostile.

    Args:
        target_filepath (Path): The target file path.
        sample_id (str): The sample ID.
        read_num (int): The read number.
        decontaminated (bool): Whether the files are decontaminated.

    Returns:
        Path: The prepared file path.
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
    """Remove a file from the filesystem.

    Args:
        file_path (Path): The path to the file to remove.
    """
    try:
        file_path.unlink()
    except OSError:
        logging.error(
            f"Failed to delete upload files created during execution, "
            f"files may still be in {file_path.parent}"
        )
    except Exception:
        pass  # A failure here doesn't matter since upload is complete
