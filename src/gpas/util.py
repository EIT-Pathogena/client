import csv
import gzip
import hashlib
import json
import logging
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

import gpas

load_dotenv()

PLATFORMS = Literal["illumina", "ont"]


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
    """Reads token from ~/.config/gpas/tokens/<host>.

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


def parse_comma_separated_string(string: str) -> set[str]:
    """Parse a comma-separated string into a set of strings.

    Args:
        string (str): The comma-separated string.

    Returns:
        set[str]: A set of parsed strings.
    """
    return set(string.strip(",").split(","))


def validate_guids(guids: set[str]) -> bool:
    """Validate a list of GUIDs.

    Args:
        guids (list[str]): The list of GUIDs to validate.

    Returns:
        bool: True if all GUIDs are valid, False otherwise.
    """
    try:
        return all(uuid.UUID(str(guid)) for guid in guids)
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
    return "GPAS_DEV_MODE" in os.environ


def display_cli_version() -> None:
    """Display the CLI version information."""
    logging.info(f"GPAS client version {gpas.__version__}")


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
        return -1
    except OSError as e:
        logging.error(f"An OS error occurred trying to open {file_path.name}: {e}")
        return -1
    except Exception as e:
        logging.error(
            f"An unexpected error occurred trying to open {file_path.name}: {e}"
        )
        return -1


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
    conf_dir = Path.home() / ".config" / "gpas"
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
