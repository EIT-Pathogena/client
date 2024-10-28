import csv
import gzip
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from types import TracebackType
from typing import Literal

import httpx
from tenacity import retry, stop_after_attempt, wait_random_exponential

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


class UnsupportedClientError(Exception):
    """Exception raised for unsupported client versions."""

    def __init__(self, this_version: str, current_version: str):
        """Raise this exception with a sensible message.

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
    """Custom exception for authorization issues. 401."""

    def __init__(self):
        """Initialize the AuthorizationError with a custom message."""
        self.message = "Authorization checks failed! Please re-authenticate with `pathogena auth` and try again.\n"
        "If the problem persists please contact support (pathogena.support@eit.org)."
        super().__init__(self.message)


class PermissionError(Exception):  # noqa: A001
    """Custom exception for permission issues. 403."""

    def __init__(self):
        """Initialize the PermissionError with a custom message."""
        self.message = (
            "You don't have access to this resource! Check logs for more details.\n"
            "Please contact support if you think you should be able to access this resource (pathogena.support@eit.org)."
        )
        super().__init__(self.message)


class MissingError(Exception):
    """Custom exception for missing issues. (HTTP Status 404)."""

    def __init__(self):
        self.message = (
            "Resource not found! It's possible you asked for something which doesn't exist. "
            "Please double check that the resource exists."
        )
        super().__init__(self.message)


class ServerSideError(Exception):
    """Custom exception for all other server side errors. (HTTP Status 5xx)."""

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


def configure_debug_logging(debug: bool) -> None:
    """Configure logging for debug mode.

    Args:
        debug (bool): Whether to enable debug logging.
    """
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Debug logging enabled")
    else:
        logging.getLogger().setLevel(logging.INFO)
        # Supress tracebacks on exceptions unless in debug mode.
        sys.excepthook = exception_handler


def exception_handler(
    exception_type: type[BaseException], exception: Exception, traceback: TracebackType
) -> None:
    """Handle uncaught exceptions by logging them.

    Args:
        exc_type (type): Exception type.
        exc_value (BaseException): Exception instance.
        exc_traceback (TracebackType): Traceback object.
    """
    logging.error(f"{exception_type.__name__}: {exception}")


def log_request(request: httpx.Request) -> None:
    """Log HTTP request details.

    Args:
        request (httpx.Request): The HTTP request object.
    """
    logging.debug(f"Request: {request.method} {request.url}")


def log_response(response: httpx.Response) -> None:
    """Log HTTP response details.

    Args:
        response (httpx.Response): The HTTP response object.
    """
    if response.is_error:
        request = response.request
        response.read()
        message = response.json().get("message")
        logging.error(f"{request.method} {request.url} ({response.status_code})")
        logging.error(message)


def raise_for_status(response: httpx.Response) -> None:
    """Raise an exception for HTTP error responses.

    Args:
        response (httpx.Response): The HTTP response object.

    Raises:
        httpx.HTTPStatusError: If the response contains an HTTP error status.
    """
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


def run(cmd: str, cwd: Path = Path()) -> subprocess.CompletedProcess:
    """Wrapper for running shell command subprocesses.

    Args:
        cmd (str): The command to run.
        cwd (Path, optional): The working directory. Defaults to Path().

    Returns:
        subprocess.CompletedProcess: The result of the command execution.
    """
    return subprocess.run(
        cmd, cwd=cwd, shell=True, check=True, text=True, capture_output=True
    )


def get_access_token(host: str) -> str:
    """Reads token from ~/.config/pathogena/tokens/<host>.

    Args:
        host (str): The host for which to retrieve the token.

    Returns:
        str: The access token.
    """
    token_path = get_token_path(host)
    logging.debug(f"{token_path=}")
    try:
        data = json.loads(token_path.read_text())
    except FileNotFoundError as fne:
        raise FileNotFoundError(
            f"Token not found at {token_path}, have you authenticated?"
        ) from fne
    return data["access_token"].strip()


def parse_csv(csv_path: Path) -> list[dict]:
    """Parse a CSV file into a list of dictionaries.

    Args:
        csv_path (Path): The path to the CSV file.

    Returns:
        list[dict]: A list of dictionaries representing the CSV rows.
    """
    with open(csv_path) as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def write_csv(records: list[dict], file_name: Path | str) -> None:
    """Write a list of dictionaries to a CSV file.

    Args:
        records (list[dict]): The data to write.
        file_name (Path | str): The path to the output CSV file.
    """
    with open(file_name, "w", newline="") as fh:
        fieldnames = records[0].keys()
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r)


def hash_file(file_path: Path) -> str:
    """Compute the SHA-256 hash of a file.

    Args:
        file_path (Path): The path to the file.

    Returns:
        str: The SHA-256 hash of the file.
    """
    hasher = hashlib.sha256()
    chunk_size = 1_048_576  # 2**20, 1MiB
    with open(Path(file_path), "rb") as fh:
        while chunk := fh.read(chunk_size):
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
    """Upload a file to the server with retries.

    Args:
        sample_id (int): The ID of the sample.
        file_path (Path): The path to the file to be uploaded.
        host (str): The host server.
        protocol (str): The protocol to use (e.g., 'http', 'https').
        checksum (str): The checksum of the file.
        dirty_checksum (str): The dirty checksum of the file.
    """
    with (
        httpx.Client(
            event_hooks=httpx_hooks,
            transport=httpx.HTTPTransport(retries=5),
            timeout=7200,  # 2 hours
        ) as client,
        open(file_path, "rb") as fh,
    ):
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
    """Upload a FASTQ file to the server.

    Args:
        sample_id (int): The ID of the sample.
        sample_name (str): The name of the sample.
        reads (Path): The path to the FASTQ file.
        host (str): The host server.
        protocol (str): The protocol to use (e.g., 'http', 'https').
        dirty_checksum (str): The dirty checksum of the file.
    """
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
    """Parse a comma-separated string into a set of strings.

    Args:
        string (str): The comma-separated string.

    Returns:
        set[str]: A set of parsed strings.
    """
    return set(string.strip(",").split(","))


def validate_guids(guids: list[str]) -> bool:
    """Validate a list of GUIDs.

    Args:
        guids (list[str]): The list of GUIDs to validate.

    Returns:
        bool: True if all GUIDs are valid, False otherwise.
    """
    for guid in guids:
        try:
            uuid.UUID(str(guid))
            return True
        except ValueError:
            return False


def map_control_value(v: str) -> bool | None:
    """Map a control value string to a boolean or None.

    Args:
        v (str): The control value string.

    Returns:
        bool | None: The mapped boolean value or None.
    """
    return {"positive": True, "negative": False, "": None}.get(v)


def is_dev_mode() -> bool:
    """Check if the application is running in development mode.

    Returns:
        bool: True if running in development mode, False otherwise.
    """
    return "PATHOGENA_DEV_MODE" in os.environ


def display_cli_version() -> None:
    """Display the CLI version information."""
    logging.info(f"EIT Pathogena client version {pathogena.__version__}")


def command_exists(command: str) -> bool:
    """Check if a command exists in the system.

    Args:
        command (str): The command to check.

    Returns:
        bool: True if the command exists, False otherwise.
    """
    try:
        result = subprocess.run(["type", command], capture_output=True)
    except FileNotFoundError:  # Catch Python parsing related errors
        return False
    return result.returncode == 0


def gzip_file(input_file: Path, output_file: str) -> Path:
    """Gzip a file and save it with a new name.

    Args:
        input_file (Path): The path to the input file.
        output_file (str): The name of the output gzipped file.

    Returns:
        Path: The path to the gzipped file.
    """
    logging.info(
        f"Gzipping file: {input_file.name} prior to upload. This may take a while depending on the size of the file."
    )
    with (
        open(input_file, "rb") as f_in,
        gzip.open(output_file, "wb", compresslevel=6) as f_out,
    ):
        shutil.copyfileobj(f_in, f_out)
    return Path(output_file)


def reads_lines_from_gzip(file_path: Path) -> int:
    """Count the number of lines in a gzipped file.

    Args:
        file_path (Path): The path to the gzipped file.

    Returns:
        int: The number of lines in the file.
    """
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
    """Count the number of lines in a FASTQ file.

    Args:
        file_path (Path): The path to the FASTQ file.

    Returns:
        int: The number of lines in the file.
    """
    try:
        with open(file_path) as contents:
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
    """Return a list of items that appear more than once in the input list.

    Args:
        inputs (list[str]): The input list.

    Returns:
        list[str]: A list of duplicate items.
    """
    seen = set()
    return [f for f in inputs if f in seen or seen.add(f)]


def get_token_path(host: str) -> Path:
    """Get the path to the token file for a given host.

    Args:
        host (str): The host for which to get the token path.

    Returns:
        Path: The path to the token file.
    """
    conf_dir = Path.home() / ".config" / "pathogena"
    token_dir = conf_dir / "tokens"
    token_dir.mkdir(parents=True, exist_ok=True)
    token_path = token_dir / f"{host}.json"
    return token_path


def get_token_expiry(host: str) -> datetime | None:
    """Get the expiry date of the token for a given host.

    Args:
        host (str): The host for which to get the token expiry date.

    Returns:
        datetime | None: The expiry date of the token, or None if the token does not exist.
    """
    token_path = get_token_path(host)
    if token_path.exists():
        try:
            with open(token_path) as token:
                token = json.load(token)
                expiry = token.get("expiry", False)
                if expiry:
                    return datetime.fromisoformat(expiry)
        except JSONDecodeError:
            return None
    return None


def is_auth_token_live(host: str) -> bool:
    """Check if the authentication token for a given host is still valid.

    Args:
        host (str): The host for which to check the token validity.

    Returns:
        bool: True if the token is still valid, False otherwise.
    """
    expiry = get_token_expiry(host)
    if expiry:
        logging.debug(f"Token expires: {expiry}")
        return expiry > datetime.now()
    return False
