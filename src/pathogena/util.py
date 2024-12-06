import csv
import gzip
import hashlib
import json
import logging
import math
import os
import shutil
import subprocess
import sys
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from types import TracebackType
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from httpx import Response
from tenacity import retry, stop_after_attempt, wait_random_exponential

import pathogena

from .batch_upload_apis import APIClient, APIError

load_dotenv()

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


class SelectedFilesType:
    """Class representing a selected file for upload."""

    def __init__(self, upload_id, batch_pk, file_data, total_chunks, upload_session):
        """Initializes a SelectedFilesType instance.

        Args:
            upload_id (str): The ID of the upload.
            batch_pk (int): The batch ID associated with the file.
            file_data (Any): The file data object.
            total_chunks (int): The total number of chunks to divide the file into.
            upload_session (int): The upload session ID.
        """
        self.upload_id = upload_id
        self.batch_pk = batch_pk
        self.file_data = file_data
        self.total_chunks = total_chunks
        self.upload_session = upload_session


class Metrics:
    """A placeholder class for the metrics associated with file uploads."""

    pass


class OnProgress:
    """A class representing the progres of a file upload."""

    def __init__(
        self, upload_id: str, batch_id: str, progress: float, metrics: Metrics
    ):
        """Initializes the OnProgress instance.

        Args:
            upload_id (str): The ID the upload.
            batch_id (str): The batch ID associated with the file upload.
            progress (float): The percentage of upload completion.
            metrics (Metrics): The metrics associated with the upload.
        """
        self.upload_id = upload_id
        self.batch_id = batch_id
        self.progress = progress
        self.metrics = metrics


class OnComplete:
    """A class representing the completion of a file upload."""

    def __init__(self, upload_id: str, batch_id: str):
        """Initializes the OnComplete instance.

        Args:
            upload_id (str): The ID the upload.
            batch_id (str): The batch ID associated with the file upload.
        """
        self.upload_id = upload_id
        self.batch_id = batch_id


class UploadFileType:
    """A class representing the parameters related to uploading files."""

    def __init__(
        self,
        access_token,
        batch_pk,
        env="api.upload-dev.eit-pathogena.com",
        files=list[SelectedFilesType],
        on_complete=Callable[[OnComplete], None],
        on_progress=Callable[[OnProgress], None],
        max_concurrent_chunks=5,
        max_concurrent_files=3,
        upload_session=None,
        abort_controller=None,
    ):
        """Initializes the UploadFileType instance.

        Args:
            access_token (str): The access token for authentication.
            batch_pk (int): The batch ID for the upload.
            env (str): The environment for the upload endpoint.
            files (list[SelectedFilesType]): A list of selected files to upload. Defaults to an empty list.
            on_complete (Callable[[OnComplete], None]): A callback function to call when the upload is complete.
            on_progress (Callable[[OnProgress], None]): A callback function to call during the upload progress.
            max_concurrent_chunks (int): The maximum number of chunks to upload concurrently. Defaults to 5.
            max_concurrent_files (int): The maximum number of files to upload concurrently. Defaults to 3.
            upload_session (int | None): The upload session ID.
            abort_controller (Any | None): An optional controller to abort the upload.
        """
        self.access_token = access_token
        self.batch_pk = batch_pk
        self.env = env
        self.files = files
        self.on_complete = on_complete
        self.on_progress = on_progress
        self.max_concurrent_chunks = max_concurrent_chunks
        self.max_concurrent_files = max_concurrent_files
        self.upload_session = upload_session
        self.abort_controller = abort_controller


def check_if_file_is_in_sample(
    sample_uploads: dict[str, dict[str, Any]] | None = None,
    file: dict[str, Any] | None = None,
) -> dict[str, Any] | bool:
    """Checks if a given file is already present in the sample uploads.

    Args:
        sample_uploads (dict[str, Dict[str, Any]]): The state of sample uploads.
        That is, a dictionary where keys are sample IDs and values are dictionaries containing sample data.
        file (dict[str, Any]): A dictionary representing the file, expected to have a 'name' key.

    Returns:
        dict[str, Any] | bool: The sample data if the file is found, else False.
    """
    # Extract samples from sample_uploads, defaulting to an empty dictionary if None
    samples = sample_uploads.get("samples") if sample_uploads else None
    if not samples or not file:
        return False

    # Iterate through sample IDs and check if the uploaded file name matches the file's name
    for _sample_id, sample_data in samples.items():
        if sample_data.get("uploaded_file_name") == file.get("name"):
            return sample_data

    return False


chunk_size = int(os.getenv("NEXT_PUBLIC_CHUNK_SIZE", 5000000))  # 5000000 = 5 mb


def prepare_file(
    file: Any,
    batch_pk: int,
    upload_session: int,
    api_client: APIClient,
    chunk_size: int = chunk_size,
) -> dict[str, Any]:
    """Prepares a file for uploading by sending metadata to initialize the process.

    Args:
        file (Any): A file object with attributes `name`, `size`, and `type`.
        batch_pk (int): The batch ID associated with the file.
        upload_session (int): The current upload session ID.
        chunk_size (int): Size of each file chunk in bytes.
        api_client (APIClient): Instance of the APIClient class.

    Returns:
        dict[str, Any]: File metadata ready for upload or error details.
    """
    original_file_name = file.name
    total_chunks = math.ceil(file.size / chunk_size)
    content_type = file.type

    form_data = {
        "original_file_name": original_file_name,
        "total_chunks": total_chunks,
        "content_type": content_type,
    }

    try:
        start = api_client.batches_uploads_start_create(
            batch_pk=batch_pk, data=form_data
        )

        if start["status"] == 200:
            upload_id = start["data"]["upload_id"]
            sample_id = start["data"]["sample_id"]

            file_ready = {
                "file": file,
                "upload_id": upload_id,
                "batch_id": batch_pk,
                "sample_id": sample_id,
                "total_chunks": total_chunks,
                "upload_session": upload_session,
            }
            return file_ready
        else:
            # Include the upload session in the error response
            start["upload_session"] = upload_session
            return start

    except APIError as e:
        # Handle any exceptions raised by the APIClient
        return {
            "error": str(e),
            "status code": e.status_code,
            "upload_session": upload_session,
        }


def prepare_files(
    batch_pk: int,
    instrument_code: str,
    files: list[dict[str, SelectedFilesType]],
    api_client: APIClient,
    sample_uploads: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepares multiple files for upload by checking credits, resuming sessions, and validating file states.

    Args:
        batch_pk (int): The ID of the batch.
        instrument_code (str): The instrument code.
        files (list[dict[str, SelectedFilesType]]): List of files to prepare.
        sample_uploads (dict[str, Any] | None): State of sample uploads, if available.
        api_client (APIClienty): Instance of the APIClient class.

    Returns:
        dict[str, Any]: Prepared file metadata, upload session information, and session data.
    """
    selected_files = []

    ## check if we have enough credits to upload the files
    batch_credit_form = {
        "samples": json.dumps(
            [
                {
                    "name": item["file"]["name"],
                    "size": item["file"]["size"],
                    "control": item["result"],
                }
                for item in files
            ]
        ),
        "instrument": instrument_code,
    }
    try:
        # check credits and start upload session
        check_credits = api_client.batches_samples_start_upload_session_create(
            batch_pk=batch_pk, data=batch_credit_form
        )
    except APIError as e:
        return {
            "API error occurred when checking credits": str(e),
            "status code": e.status_code,
        }

    if not check_credits.get("data", {}).get("upload_session"):
        # Log if the upload session could not be resumed
        logging.error("Upload session cannot be resumed. Please create a new batch.")
        return

    # Upload session
    upload_session = check_credits["data"]["upload_session"]

    for item in files:
        sample = check_if_file_is_in_sample(sample_uploads, item["file"])
        if (
            sample
            and sample.get("upload_status") != "COMPLETE"
            and sample.get("total_chunks", 0) > 0
        ):
            # File not already uploaded, add to selected files
            selected_files.append(
                {
                    "file": item["file"],
                    "upload_id": sample.get("upload_id"),
                    "batch_id": batch_pk,
                    "sample_id": sample.get("id"),
                    "total_chunks": sample.get("metrics", {}).get(
                        "chunks_total", sample.get("total_chunks", 0)
                    ),
                    "estimated_completion_time": sample.get("metrics", {}).get(
                        "estimated_completion_time"
                    ),
                    "time_remaining": sample.get("metrics", {}).get("time_remaining"),
                    "uploadSession": upload_session,
                }
            )
        elif sample and sample.get("upload_status") == "COMPLETE":
            # Log that the file has already been uploaded, don't add to selected files
            logging.info(f"File '{item['file']['name']}' has already been uploaded.")
        else:
            # Prepare new file and add to selected files
            file_ready = prepare_file(
                item["file"], batch_pk, upload_session, api_client
            )
            if file_ready:
                selected_files.append(file_ready)

    return {
        "files": selected_files,
        "uploadSession": upload_session,
        "uploadSessionData": check_credits["data"],
    }


@retry(wait=wait_random_exponential(multiplier=2, max=60), stop=stop_after_attempt(10))
def upload_chunk(
    batch_pk: int,
    host: str,
    protocol: str,
    checksum: str,
    dirty_checksum: str,
    chunk: bytes,
    chunk_index: int,
) -> Response:
    """Upload a single file chunk.

    Args:
        batch_pk (int): ID of sample to upload
        host (str): pathogena host, e.g api.upload-dev.eit-pathogena.com
        protocol (str): protocol, default https
        checksum (str): sample metadata if decontaminated
        dirty_checksum (str): sample metadata pre-decontimation
        chunk (bytes): File chunk to be uploaded
        chunk_index (int): Index representing what chunk of the whole
        sample file this chunk is from 0...total_chunks

    Returns:
        Response: The response object from the HTTP POST request conatining
        the status code and content from the server.
    """
    try:
        with httpx.Client(
            event_hooks=httpx_hooks,
            transport=httpx.HTTPTransport(retries=5),
            timeout=7200,  # 2 hours
        ) as client:
            response = client.post(
                f"{protocol}://{host}/api/v1/batches/{batch_pk}/uploads/upload-chunk/",
                headers={"Authorization": f"Bearer {get_access_token(host)}"},
                files={"file": chunk},
                data={
                    "checksum": checksum,
                    "dirty_checksum": dirty_checksum,
                    "chunk_index": chunk_index,
                },
            )
            if response.status_code >= 400:
                logging.error(
                    f"Error uploading chunk {chunk_index} of batch {batch_pk}: {response.text}"
                )
                return response
            else:
                return response
    except Exception as e:
        logging.error(
            f"Exception while uploading chunk {chunk_index} of batch {batch_pk}: {str(e)}"
        )
        raise


def process_queue(chunk_queue: list, max_concurrent_chunks: int) -> None:
    """Processes a queue of chunks concurrently to ensure tno more than 'max_concurrent_chunks' are processed at the same time.

    Args:
        chunk_queue (list): A collection of futures (generated by thread pool executor)
        representing the chunks to be processed.
        max_concurrent_chunks (int): The maximum number of chunks to be processed concurrently.
    """
    if len(chunk_queue) >= max_concurrent_chunks:
        for future in as_completed(chunk_queue):
            future.result()


# upload_all chunks of a file
def upload_chunks(
    upload_data: UploadFileType, file: SelectedFilesType, file_status: dict
) -> None:
    """Uploads chunks of a single file.

    Args:
        upload_data (UploadFileType): The upload data including batch_id, session info, etc.
        file (SelectedFilesType): The file to upload (with file data, total chunks, etc.)
        file_status (dict): The dictionary to track the file upload progress.

    Returns:
        None: This function does not return anything, but updates the `file_status` dictionary
            and calls the provided `on_progress` and `on_complete` callback functions.
    """
    chunks_uploaded = 0
    chunk_queue = []
    stop_uploading = False

    for i in range(file.total_chunks):  # total chunks = file.size/chunk_size
        # stop uploading chunks if one returns a 400 error
        if stop_uploading:
            break

        process_queue()

        # chunk the files
        start = i * chunk_size  # 5 MB chunk size default
        end = start + chunk_size
        file_chunk = file.file_data[start:end]

        # upload chunk
        chunk_upload = upload_chunk(
            batch_pk=upload_data.batch_pk,
            host=upload_data.env,
            protocol="https",
            checksum="checksum",
            dirty_checksum="dirty_checksum",
            chunk=file_chunk,
            chunk_index=i,
        )
        chunk_queue.append(chunk_upload)

        try:
            # get result of upload chunk
            chunk_upload_result = chunk_upload.result()

            # stop uploading subsequent chunks if upload chunk retuns a 400
            if chunk_upload_result.status_code == 400:
                logging.error(
                    f"Chunk upload failed for chunk {i} of batch {upload_data.batch_pk}. Response: {chunk_upload_result.text}"
                )
                stop_uploading = True
                break

            # process result of chunk upload for upload chunks that don't return 400 status
            if chunk_upload and chunk_upload["data"]["metrics"]:
                chunks_uploaded += 1
                file_status[file.upload_id] = {
                    "chunks_uploaded": chunks_uploaded,
                    "total_chunks": file.total_chunks,
                    "metrics": chunk_upload["data"]["metrics"],
                }
                progress = (chunks_uploaded / file.total_chunks) * 100
                upload_data.on_progress(
                    file.upload_id,
                    file.batch_id,
                    progress,
                    chunk_upload["data"]["metrics"],
                )

                # If all chunks have been uploaded, complete the file upload

                if chunks_uploaded == file.total_chunks:
                    upload_data.on_complete(file.upload_id, file.batch_id)
                    end_status = end_upload(file.batch_id, file.upload_id)
                    if end_status["status"] == 400:
                        logging.error(
                            f"Failed to end upload for file: {file.upload_id} (Batch ID: {file.batch_id})"
                        )

        except Exception as e:
            logging.error(
                f"Error uploading chunk {i} of batch {upload_data.batch_pk}: {str(e)}"
            )
            stop_uploading = (
                True  # Stop uploading further chunks if some other error occurs
            )
            break


def upload_files(
    upload_data: UploadFileType,
    instrument_code: str,
    api_client: APIClient,
    sample_uploads: dict[str, Any] | None = None,
) -> None:
    """Uploads files in chunks and manages the upload process.

    This function first prepares the files for upload, then uploads them in chunks
    using a thread pool executor for concurrent uploads. It finishes by ending the
    upload session.

    Args:
        upload_data (UploadFileType): An object containing the upload configuration,
            including the batch ID, access token, environment, and file details.
        instrument_code (str): The instrument code used to generate the data. This is
            passed to the backend API for processing.
        api_client (APIClient): Instance of the APIClient class.
        sample_uploads (dict[str, Any] | None): State of sample uploads, if available.

    Returns:
        None
    """
    file_status = {}

    # prepare files before uploading
    file_preparation = prepare_files(
        batch_pk=upload_data.batch_pk,
        instrument_code=instrument_code,
        files=upload_data.files,
        api_client=api_client,
        sample_uploads=sample_uploads,
    )

    # handle any errors during preparation
    if "API error occurred" in file_preparation:
        logging.error(
            f"Error preparing files: {file_preparation['API error occurred']}"
        )
        return file_preparation

    # files have been sucessfully prepared, extract the prepared file list
    selected_files = file_preparation["files"]

    # upload the file chunks
    with ThreadPoolExecutor(max_workers=upload_data.max_concurrent_chunks) as executor:
        futures = []
        for file in selected_files:
            file = file["file"]
            future = executor.submit(upload_chunks, upload_data, file, file_status)
            futures.append(future)

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logging.error(f"Error uploading file: {e}")

    # end the upload session
    end_session = APIClient.batches_samples_end_upload_session_create(
        upload_data.batch_pk, upload_data
    )

    if end_session["status"] != 200:
        logging.error(f"Failed to end upload session for batch {upload_data.batch_id}.")
    else:
        logging.info(f"All uploads complete.")


def end_upload(batch_pk: int, file_id: str) -> dict[str, Any]:
    """End the upload of a sample.

    Args:
        batch_pk (int):ID of the uploaded sample.
        upload_session (int): ID of the upload session.

    Returns:
        dict[str, Any]: The response JSON from the API.
    """
    data = {"upload_id": file_id}

    return APIClient.batches_uploads_end_create(batch_pk, data)


def end_upload_session(batch_pk: int, upload_session: int) -> dict[str, Any]:
    """End the upload session.

    Args:
        batch_pk (int):ID of the uploaded sample.
        upload_session (int): ID of the upload session.

    Returns:
        dict[str, Any]: The response JSON from the API.
    """
    data = {"upload_session": upload_session}
    return APIClient.batches_samples_end_upload_session_create(batch_pk, data)


def upload_fastq(
    batch_pk: int,
    sample_name: str,
    reads: Path,
    upload_data: UploadFileType,
    instrument_code: str,
) -> None:
    """Upload a FASTQ file to the server.

    Args:
        batch_pk (int): The ID of the sample.
        sample_name (str): The name of the sample.
        reads (Path): The path to the FASTQ file.
        upload_data (UploadFileType): The upload data including batch_id, session info, etc.
        instrument_code (str): The instument code used to take sample.
    """
    reads = Path(reads)
    logging.debug(f"upload_fastq(): {batch_pk=}, {sample_name=}, {reads=}")
    logging.info(f"Uploading {sample_name}")
    # checksum = hash_file(reads)
    upload_files(upload_data, instrument_code)
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
