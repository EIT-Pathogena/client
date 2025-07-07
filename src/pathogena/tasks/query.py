import csv
import logging
from pathlib import Path

import httpx
import tqdm
from packaging.version import Version

import pathogena
from pathogena import models, util
from pathogena.client.env import get_access_token, get_host, get_protocol
from pathogena.constants import DEFAULT_HOST
from pathogena.errors import UnsupportedClientError
from pathogena.log_utils import httpx_hooks


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
    return samples_status  # type: ignore


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
    headers = {"Authorization": f"Bearer {get_access_token(host)}"}
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


def fetch_sample(sample_id: str, host: str) -> dict:
    """Fetch sample data from the server.

    Args:
        sample_id (str): The sample ID.
        host (str): The host server.

    Returns:
        dict: The sample data.
    """
    headers = {"Authorization": f"Bearer {get_access_token(host)}"}
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
