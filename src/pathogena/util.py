import csv
import gzip
import hashlib
import json
import logging
import os
import shutil
import subprocess
import uuid
import sys
from datetime import datetime
from json import JSONDecodeError

from tenacity import retry, wait_random_exponential, stop_after_attempt

from pathlib import Path
from typing import Literal

import httpx

import pathogena

PLATFORMS = Literal["illumina", "ont"]


class InvalidPathError(Exception):
    """Custom exception for giving nice user errors around missing paths."""

    def __init__(self, message: str):
        """Constructor, used to pass a custom message to user.

        Args:
            message (str): Message about this path
        """
        self.message = message
        super().__init__(self.message)


class UnsupportedClientException(Exception):
    """Exception raised for unsupported client versions"""

    def __init__(self, this_version: str, current_version: str):
        """Raise this exception with a sensible message
        Args:
            this_version (str): The version of installed version
            current_version (str): The version returned by the API
        """
        self.message = (
            f"\n\nThe installed client version ({this_version}) is no longer supported."
            " To update the client, please run:\n\n"
            "conda create -y -n pathogena -c conda-forge -c bioconda hostile==1.1.0 && conda activate pathogena && pip install --upgrade pathogena"
        )
        super().__init__(self.message)


# Python errors for neater client errors
class AuthorizationError(Exception):
    """Custom exception for authorization issues. 401"""

    def __init__(self):
        self.message = "Authorization checks failed! Please re-authenticate with `pathogena auth` and try again.\n"
        "If the problem persists please contact support (pathogena.support@eit.org)."
        super().__init__(self.message)


class PermissionError(Exception):
    """Custom exception for permission issues. 403"""

    def __init__(self):
        self.message = (
            "You don't have access to this resource! Check logs for more details.\n"
            "Please contact support if you think you should be able to access this resource (pathogena.support@eit.org)."
        )
        super().__init__(self.message)


class MissingError(Exception):
    """Custom exception for missing issues. 404"""

    def __init__(self):
        self.message = (
            "Resource not found! It's possible you asked for something which doesn't exist. "
            "Please double check that the resource exists."
        )
        super().__init__(self.message)


class ServerSideError(Exception):
    """Custom exception for all other server side errors. 5xx"""

    def __init__(self):
        self.message = (
            "We had some trouble with the server, please double check your command and try again in a moment.\n"
            "If the problem persists, please contact support (pathogena.support@eit.org)."
        )
        super().__init__(self.message)


class InsufficientFundsError(Exception):
    """Custom exception for insufficient funds."""

    def __init__(self):
        self.message = (
            "Your account doesn't have enough credits to fulfil the number of Samples in your Batch. "
            "You can request more credits by contacting support (pathogena.support@eit.org)."
        )
        super().__init__(self.message)


def configure_debug_logging(debug: bool):
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Debug logging enabled")
    else:
        logging.getLogger().setLevel(logging.INFO)
        # Supress tracebacks on exceptions unless in debug mode.
        sys.excepthook = exception_handler


def exception_handler(exception_type, exception, traceback):
    logging.error(f"{exception_type.__name__}: {exception}")


def log_request(request):
    logging.debug(f"Request: {request.method} {request.url}")


def log_response(response):
    if response.is_error:
        request = response.request
        response.read()
        message = response.json().get("message")
        logging.error(f"{request.method} {request.url} ({response.status_code})")
        logging.error(message)


def raise_for_status(response: httpx.Response):
    if response.is_error:
        response.read()
        if response.status_code == 401:
            logging.error("Have you tried running `pathogena auth`?")
            raise AuthorizationError()
        elif response.status_code == 402:
            raise InsufficientFundsError()
        elif response.status_code == 403:
            raise PermissionError()
        elif response.status_code == 404:
            raise MissingError()
        elif response.status_code // 100 == 5:
            raise ServerSideError()

    # Default to httpx errors in other cases
    response.raise_for_status()


httpx_hooks = {"request": [log_request], "response": [log_response, raise_for_status]}


def run(cmd: str, cwd: Path = Path()):
    return subprocess.run(
        cmd, cwd=cwd, shell=True, check=True, text=True, capture_output=True
    )


def get_access_token(host: str) -> str:
    """Reads token from ~/.config/pathogena/tokens/<host>"""
    token_path = get_token_path(host)
    logging.debug(f"{token_path=}")
    try:
        data = json.loads(token_path.read_text())
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Token not found at {token_path}, have you authenticated?"
        )
    return data["access_token"].strip()


def parse_csv(csv_path: Path) -> list[dict]:
    """Parse CSV returning a list of dictionaries"""
    with open(csv_path, "r") as fh:
        reader = csv.DictReader(fh)
        return [row for row in reader]


def write_csv(records: list[dict], file_name: Path | str) -> None:
    """Write a list of dictionaries to a CSV file"""
    with open(file_name, "w", newline="") as fh:
        fieldnames = records[0].keys()
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r)


def hash_file(file_path: Path) -> str:
    hasher = hashlib.sha256()
    CHUNK_SIZE = 1_048_576  # 2**20, 1MiB
    with open(Path(file_path), "rb") as fh:
        while chunk := fh.read(CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


@retry(wait=wait_random_exponential(multiplier=2, max=60), stop=stop_after_attempt(10))
def upload_file(
    sample_id: int,
    file_path: Path,
    host: str,
    protocol: str,
    checksum: str,
    dirty_checksum: str,
) -> None:
    with httpx.Client(
        event_hooks=httpx_hooks,
        transport=httpx.HTTPTransport(retries=5),
        timeout=7200,  # 2 hours
    ) as client:
        with open(file_path, "rb") as fh:
            client.post(
                f"{protocol}://{host}/api/v1/samples/{sample_id}/files",
                headers={"Authorization": f"Bearer {get_access_token(host)}"},
                files={"file": fh},
                data={"checksum": checksum, "dirty_checksum": dirty_checksum},
            )


def upload_fastq(
    sample_id: int,
    sample_name: str,
    reads: Path,
    host: str,
    protocol: str,
    dirty_checksum: str,
) -> None:
    """Upload FASTQ file to server"""
    reads = Path(reads)
    logging.debug(f"upload_fastq(): {sample_id=}, {sample_name=}, {reads=}")
    logging.info(f"Uploading {sample_name}")
    checksum = hash_file(reads)
    upload_file(
        sample_id,
        reads,
        host=host,
        protocol=protocol,
        checksum=checksum,
        dirty_checksum=dirty_checksum,
    )
    logging.info(f"  Uploaded {reads.name}")


def parse_comma_separated_string(string) -> set[str]:
    return set(string.strip(",").split(","))


def validate_guids(guids: list[str]) -> bool:
    for guid in guids:
        try:
            uuid.UUID(str(guid))
            return True
        except ValueError:
            return False


def map_control_value(v: str) -> bool | None:
    return {"positive": True, "negative": False, "": None}.get(v)


def is_dev_mode() -> bool:
    return True if "PATHOGENA_DEV_MODE" in os.environ else False


def display_cli_version() -> None:
    logging.info(f"EIT Pathogena client version {pathogena.__version__}")


def command_exists(command: str) -> bool:
    try:
        result = subprocess.run(
            ["type", command], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except FileNotFoundError:  # Catch Python parsing related errors
        return False
    return result.returncode == 0


def gzip_file(input_file: Path, output_file: str) -> Path:
    logging.info(
        f"Gzipping file: {input_file.name} prior to upload. This may take a while depending on the size of the file."
    )
    with open(input_file, "rb") as f_in:
        with gzip.open(output_file, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)
    return Path(output_file)


def reads_lines_from_gzip(file_path: Path) -> int:
    line_count = 0
    # gunzip offers a ~4x faster speed when opening GZip files, use it if we can.
    if command_exists("gunzip"):
        logging.debug("Reading lines using gunzip")
        result = subprocess.run(
            ["gunzip", "-c", file_path.as_posix()], stdout=subprocess.PIPE, text=True
        )
        line_count = result.stdout.count("\n")
    if line_count == 0:  # gunzip didn't work, try the long method
        logging.debug("Using gunzip failed, using Python's gzip implementation")
        try:
            with gzip.open(file_path, "r") as contents:
                line_count = sum(1 for _ in contents)
        except gzip.BadGzipFile as e:
            logging.error(f"Failed to open the Gzip file: {e}")
    return line_count


def reads_lines_from_fastq(file_path: Path) -> int:
    try:
        with open(file_path, "r") as contents:
            line_count = sum(1 for _ in contents)
        return line_count
    except PermissionError:
        logging.error(
            f"You do not have permission to access this file {file_path.name}."
        )
    except OSError as e:
        logging.error(f"An OS error occurred trying to open {file_path.name}: {e}")
    except Exception as e:
        logging.error(
            f"An unexpected error occurred trying to open {file_path.name}: {e}"
        )


def find_duplicate_entries(inputs: list[str]) -> list[str]:
    """Return a set of items that appear more than once in the input list."""
    seen = set()
    return [f for f in inputs if f in seen or seen.add(f)]


def get_token_path(host: str) -> Path:
    conf_dir = Path.home() / ".config" / "pathogena"
    token_dir = conf_dir / "tokens"
    token_dir.mkdir(parents=True, exist_ok=True)
    token_path = token_dir / f"{host}.json"
    return token_path


def get_token_expiry(host: str) -> datetime | None:
    token_path = get_token_path(host)
    if token_path.exists():
        try:
            with open(token_path, "r") as token:
                token = json.load(token)
                expiry = token.get("expiry", False)
                if expiry:
                    return datetime.fromisoformat(expiry)
        except JSONDecodeError:
            return None
    return None


def is_auth_token_live(host: str) -> bool:
    expiry = get_token_expiry(host)
    if expiry:
        logging.debug(f"Token expires: {expiry}")
        return expiry > datetime.now()
    return False
