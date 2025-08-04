import logging
from pathlib import Path
from typing import Any

import httpx
from hostile.lib import ALIGNER
from hostile.util import BUCKET_URL, CACHE_DIR
from tenacity import retry, stop_after_attempt, wait_random_exponential
from tqdm import tqdm

from pathogena import models, util
from pathogena.client import env
from pathogena.constants import DEFAULT_HOST, HOSTILE_INDEX_NAME
from pathogena.errors import MissingError
from pathogena.log_utils import httpx_hooks
from pathogena.tasks.query import (
    check_version_compatibility,
    fetch_output_files,
    parse_csv,
)


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
    headers = {"Authorization": f"Bearer {env.get_access_token(host)}"}
    guids_samples: dict[str, Any | None]
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
                        f"{env.get_protocol()}://{host}/api/v1/"
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
                        f"{env.get_protocol()}://{host}/api/v1/"
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


def fetch_latest_input_files(sample_id: str, host: str) -> dict[str, models.RemoteFile]:
    """Return models.RemoteFile instances for a sample input files.

    Args:
        sample_id (str): The sample ID.
        host (str): The host server.

    Returns:
        dict[str, models.RemoteFile]: The latest input files.
    """
    headers = {"Authorization": f"Bearer {env.get_access_token(host)}"}
    with httpx.Client(
        event_hooks=httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
    ) as client:
        response = client.get(
            f"{env.get_protocol()}://{host}/api/v1/samples/{sample_id}/latest/input-files",
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
