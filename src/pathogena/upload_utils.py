import logging
import math
import os
import sys
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TypedDict

import httpx
from httpx import Response, codes
from tenacity import retry, stop_after_attempt, wait_random_exponential

from pathogena.batch_upload_apis import APIError, UploadAPIClient
from pathogena.constants import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_HOST,
    DEFAULT_MAX_UPLOAD_RETRIES,
    DEFAULT_PROTOCOL,
    DEFAULT_RETRY_DELAY,
    DEFAULT_UPLOAD_HOST,
)
from pathogena.log_utils import httpx_hooks
from pathogena.models import UploadSample
from pathogena.util import get_access_token


def get_protocol() -> str:
    """Get the protocol to use for communication.

    Returns:
        str: The protocol (e.g., 'http', 'https').
    """
    protocol = os.environ.get("PATHOGENA_PROTOCOL")
    if protocol is not None:
        return protocol
    else:
        return DEFAULT_PROTOCOL


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


class SampleFileMetadata(TypedDict):
    """A TypedDict representing metadata for a file upload.

    Args:
        name: The name of the sample file
        size: The size of the sample file in bytes
        content_type: The content type
        specimen_organism: The organism from which the sample was taken
    """

    name: str
    size: int
    content_type: str
    specimen_organism: str
    resolved_path: Path | None
    control: str


class UploadMetrics(TypedDict):
    """A TypedDict representing metrics for file upload progress and status.

    Args:
        chunks_received: Number of chunks successfully received by the server
        chunks_total: Total number of chunks expected for the complete file
        upload_status: Current status of the upload (e.g. "in_progress", "complete")
        percentage_complete: Upload progress as a percentage from 0 to 100
        upload_speed: Current upload speed in bytes per second
        time_remaining: Estimated time remaining for upload completion in seconds
        estimated_completion_time: Predicted datetime when upload will complete
    """

    chunks_received: int
    chunks_total: int
    upload_status: str
    percentage_complete: float
    upload_speed: float
    time_remaining: float
    estimated_completion_time: datetime


class SampleFileUploadStatus(TypedDict):
    """A TypedDict representing the status and metadata of a sample file upload.

    Args:
        id: Unique identifier for the sample file
        batch: ID of the batch this sample belongs to
        file_path: Path to the uploaded file on the server
        uploaded_file_name: Original name of the uploaded file
        generated_name: System-generated name for the file
        created_at: Timestamp when the upload was created
        upload_status: Current status of the upload (IN_PROGRESS/COMPLETE/FAILED)
        total_chunks: Total number of chunks for this file
        upload_id: Unique identifier for this upload session
        legacy_sample_id: Original sample ID from legacy system
        metrics: Upload metrics including progress and performance data
    """

    id: int
    batch: int
    file_path: str
    uploaded_file_name: str
    generated_name: str
    created_at: datetime
    upload_status: Literal["IN_PROGRESS", "COMPLETE", "FAILED"]
    total_chunks: int
    upload_id: str
    legacy_sample_id: str
    metrics: UploadMetrics


class BatchUploadStatus(TypedDict):
    """A TypedDict representing the status of a batch upload and its sample files.

    Args:
        upload_status: Current status of the batch upload (e.g. "in_progress", "complete")
        sample_files: Dictionary mapping sample file IDs to their individual upload statuses
    """

    upload_status: str
    sample_files: dict[str, SampleFileUploadStatus]


class SelectedFile(TypedDict):
    """A TypedDict representing a file selected for upload with its metadata.

    Args:
        file: Dictionary containing file information with string keys and values
        upload_id: Unique identifier for the upload
        batch_pk: Primary key of the batch this file belongs to
        sample_id: Identifier for the sample associated with this file
        sample_file_id: Identifier for the sample_file associated with this file
        total_chunks: Total number of chunks the file will be split into
        estimated_completion_time: Estimated time in seconds until upload completes
        time_remaining: Time remaining in seconds for the upload
        uploadSession: Identifier for the current upload session
        file_data: The actual file data to be uploaded
        total_chunks: Total number of chunks for this file
    """

    file: dict[str, str]
    upload_id: int
    batch_pk: int
    sample_id: str
    sample_file_id: int
    total_chunks: int
    estimated_completion_time: int
    time_remaining: int
    uploadSession: int
    file_data: Any
    total_chunks: int


class PreparedFiles(TypedDict):
    """A TypedDict representing the prepared files and upload session data.

    Args:
        files: List of SelectedFile objects containing file metadata and upload details
        uploadSession: Unique identifier for the current upload session
        uploadSessionData: Dictionary containing additional metadata about the upload session
    """

    files: list[SelectedFile]
    uploadSession: int
    uploadSessionData: dict[str, Any]


@dataclass
class Metrics:
    """A placeholder class for the metrics associated with file uploads."""

    ...


@dataclass
class OnProgress:
    """Initializes the OnProgress instance.

    Args:
        upload_id (int): The ID the upload.
        batch_pk (int): The batch ID associated with the file upload.
        progress (float): The percentage of upload completion.
        metrics (UploadMetrics): The metrics associated with the upload.
    """

    upload_id: int
    batch_pk: int
    progress: float
    metrics: UploadMetrics


@dataclass
class OnComplete:
    """Initializes the OnComplete instance.

    Args:
        upload_id (int): The ID the upload.
        batch_pk (int): The batch ID associated with the file upload.
    """

    upload_id: int
    batch_pk: int


@dataclass
class UploadData:
    """A class representing the parameters related to uploading files."""

    def __init__(
        self,
        access_token,
        batch_pk,
        env,
        samples: list[UploadSample],
        on_complete: OnComplete | None = None,
        on_progress: OnProgress | None = None,
        max_concurrent_chunks: int = 5,
        max_concurrent_files: int = 3,
        upload_session=None,
        abort_controller=None,
    ):
        """Initializes the UploadFileType instance.

        Args:
            access_token (str): The access token for authentication.
            batch_pk (str): The batch ID for the upload.
            env (str): The environment for the upload endpoint.
            samples (list[UploadSample]): A list of samples to upload. Defaults to an empty list.
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
        self.samples = samples
        self.on_complete = on_complete
        self.on_progress = on_progress
        self.max_concurrent_chunks = max_concurrent_chunks
        self.max_concurrent_files = max_concurrent_files
        self.upload_session = upload_session
        self.abort_controller = abort_controller


def get_upload_host(cli_host: str | None = None) -> str:
    """Return hostname using 1) CLI argument, 2) environment variable, 3) default value.

    Args:
        cli_host (str | None): The host provided via CLI argument.

    Returns:
        str: The resolved hostname.
    """
    return (
        cli_host
        if cli_host is not None
        else os.environ.get("PATHOGENA_UPLOAD_HOST", DEFAULT_UPLOAD_HOST)
    )


def get_batch_upload_status(
    batch_pk: str,
) -> BatchUploadStatus:
    """Starts an upload by making a POST request.

    Args:
        batch_pk (int): The primary key of the batch.
        data (dict[str, Any] | None): Data to include in the POST request body.

    Returns:
        dict[str, Any]: The response JSON from the API.

    Raises:
        APIError: If the API returns a non-2xx status code.
    """
    api = UploadAPIClient()
    url = f"{get_protocol()}://{api.base_url}/api/v1/batches/{batch_pk}/state"
    try:
        response = api.client.get(
            url, headers={"Authorization": f"Bearer {api.token}"}, follow_redirects=True
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        raise APIError(
            f"Failed to fetch batch status: {response.text}",
            response.status_code,
        ) from e


def get_file_data_from_resolved_path(reads_resolved_path: Path | None):
    """Get the file name, content type, and Path object based on a resolved file path.

    Args:
        reads_resolved_path (Path | None): Path to the file to inspect.

    Returns:
        tuple[str, str, Path | None]:
            name: The file's name, or an empty string if the path is None or doesn't exist.
            content_type: "application/gzip" if the file suffix is 'gzip' or 'gz'; otherwise "text/plain".
            resolved_path: The Path object if the file exists; otherwise None.
    """
    if reads_resolved_path is None or not reads_resolved_path.exists():
        return "", "text/plain", None

    return (
        reads_resolved_path.name,
        "application/gzip"
        if reads_resolved_path.suffix in ("gzip", "gz")
        else "text/plain",
        reads_resolved_path,
    )


def prepare_files(
    batch_pk: str,
    samples: list[UploadSample],
    api_client: UploadAPIClient,
) -> PreparedFiles:
    """Prepares multiple files for upload.

    This function starts the upload session, checks the upload status of the current
    sample and if it has not already been uploaded or partially uploaded prepares
    the sample from scratch.

    Args:
        batch_pk (str): The ID of the batch.
        samples (list[UploadSample]): List of samples to prepare the files for.
        api_client (UploadAPIClient): Instance of the APIClient class.

    Returns:
        PreparedFiles: Prepared file metadata, upload session information, and session data.
    """
    selected_files = []

    # create file metadata depending on if illumina or ont
    files: list[SampleFileMetadata] = []
    for sample in samples:
        if sample.is_illumina():
            file1_name, file1_content_type, file1_resolved_path = (
                get_file_data_from_resolved_path(sample.reads_1_resolved_path)
            )
            file2_name, file2_content_type, file2_resolved_path = (
                get_file_data_from_resolved_path(sample.reads_2_resolved_path)
            )
            files.append(
                {
                    "name": file1_name,
                    "size": sample.file1_size,
                    "control": sample.control.upper(),
                    "content_type": file1_content_type,
                    "specimen_organism": sample.specimen_organism,
                    "resolved_path": file1_resolved_path,
                }
            )
            files.append(
                {
                    "name": file2_name,
                    "size": sample.file2_size,
                    "control": sample.control.upper(),
                    "content_type": file2_content_type,
                    "specimen_organism": sample.specimen_organism,
                    "resolved_path": file2_resolved_path,
                }
            )
        else:
            file1_name, file1_content_type, file1_resolved_path = (
                get_file_data_from_resolved_path(sample.reads_1_resolved_path)
            )
            files.append(
                {
                    "name": file1_name,
                    "size": sample.file1_size,
                    "control": sample.control.upper(),
                    "content_type": file1_content_type,
                    "specimen_organism": sample.specimen_organism,
                    "resolved_path": file1_resolved_path,
                }
            )

    # create payload for starting upload session from sample metadata
    files_to_upload = []
    for file in files:
        file_payload = {
            "original_file_name": file.get("name"),
            "file_size_in_kb": file.get("size"),
        }

        if file.get("specimen_organism"):
            file_payload["specimen_organism"] = file.get("specimen_organism")

        files_to_upload.append(file_payload)

    form_details = {
        "files_to_upload": files_to_upload,
        "specimen_organism": files[0].get("specimen_organism"),
    }

    try:
        session_response = api_client.batches_samples_start_upload_session_create(
            batch_pk=batch_pk, data=form_details
        )
    except APIError as e:
        raise APIError(
            f"Error starting session: {str(e)}",
            e.status_code,
        ) from e

    if not session_response["upload_session"]:
        # Log if the upload session could not be resumed
        logging.exception(
            "Upload session cannot be resumed. Please create a new batch."
        )
        raise APIError(
            "No upload session returned by the API.", codes.INTERNAL_SERVER_ERROR
        )

    upload_session = session_response["upload_session"]
    sample_summaries = session_response["sample_summaries"]

    # assume order is consistent and map out the sample summaries to the files
    # ie. illumina samples have two files and ont samples have one
    per_file_sample_summaries = (
        [item for item in sample_summaries for _ in range(2)]
        if len(sample_summaries) * 2 == len(files_to_upload)
        else sample_summaries
    )

    for idx, file_metadata in enumerate(files):
        sample_id = per_file_sample_summaries[idx].get("sample_id")

        file_ready = prepare_file(
            resolved_path=file_metadata["resolved_path"],
            file_metadata=file_metadata,
            batch_pk=batch_pk,
            upload_session=upload_session,
            sample_id=sample_id,
            api_client=api_client,
        )
        if file_ready:
            selected_files.append(file_ready)

    return {
        "files": selected_files,
        "uploadSession": upload_session,
        "uploadSessionData": session_response,
    }


# upload_all chunks of a file
def upload_chunks(
    upload_data: UploadData,
    file: SelectedFile,
    file_status: dict,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> None:
    """Uploads chunks of a single file.

    Args:
        upload_data (UploadData): The upload data including batch_id, session info, etc.
        file (SelectedFile): The file to upload (with file data, total chunks, etc.)
        file_status (dict): The dictionary to track the file upload progress.
        chunk_size (int): Default size of file chunk to upload (5mb)

    Returns:
        None: This function does not return anything, but updates the `file_status` dictionary
            and calls the provided `on_progress` and `on_complete` callback functions.
    """
    logging.info(f"Uploading {file['file']['name']}")
    chunks_uploaded = 0
    chunk_queue = []
    stop_uploading = False

    max_retries = DEFAULT_MAX_UPLOAD_RETRIES
    retry_delay = DEFAULT_RETRY_DELAY
    for i in range(file["total_chunks"]):  # total chunks = file.size/chunk_size
        if stop_uploading:
            break

        process_queue(chunk_queue, upload_data.max_concurrent_chunks)

        # chunk the files
        start = i * chunk_size  # 5 MB chunk size default
        end = start + chunk_size
        file_chunk = file["file_data"][start:end]

        success = False
        attempt = 0

        while attempt < max_retries and not success:
            chunk_upload = upload_chunk(
                batch_pk=upload_data.batch_pk,
                host=get_host(),
                protocol=get_protocol(),
                chunk=file_chunk,
                chunk_index=i,
                upload_id=file["upload_id"],
            )
            chunk_queue.append(chunk_upload)
            try:
                chunk_upload_result = chunk_upload.json()

                if chunk_upload.status_code >= 400:
                    logging.error(
                        f"Attempt {attempt + 1} of {max_retries}: Chunk upload failed for chunk {i} of batch {upload_data.batch_pk}. Response: {chunk_upload_result.text}"
                    )
                    attempt += 1

                    if attempt < max_retries:
                        logging.info(f"Retrying upload of chunk {i}")
                        time.sleep(retry_delay)
                        continue
                    else:
                        stop_uploading = (
                            True  # stop retrying if have reached max retry attempts
                        )
                        break

                # process result of chunk upload for upload chunks that don't return 400 status
                metrics = chunk_upload_result.get("metrics", {})
                if metrics:
                    chunks_uploaded += 1
                    file_status[file["upload_id"]] = {
                        "chunks_uploaded": chunks_uploaded,
                        "total_chunks": file["total_chunks"],
                        "metrics": chunk_upload_result["metrics"],
                    }
                    progress = (chunks_uploaded / file["total_chunks"]) * 100

                    # Create an OnProgress instance
                    progress_event = OnProgress(
                        upload_id=file["upload_id"],
                        batch_pk=upload_data.batch_pk,
                        progress=progress,
                        metrics=chunk_upload_result["metrics"],
                    )
                    upload_data.on_progress = progress_event

                    # If all chunks have been uploaded, complete the file upload
                    if chunks_uploaded == file["total_chunks"]:
                        complete_event = OnComplete(
                            file["upload_id"], upload_data.batch_pk
                        )
                        upload_data.on_complete = complete_event
                        client = UploadAPIClient()
                        end_status = client.batches_uploads_end_file_upload(
                            upload_data.batch_pk,
                            data={"upload_id": file["upload_id"]},
                        )
                        if end_status.status_code == 400:
                            logging.error(
                                f"Failed to end upload for file: {file['upload_id']} (Batch ID: {upload_data.batch_pk})"
                            )
                success = True

            except Exception as e:
                logging.error(
                    f"Attempt {attempt + 1} of {max_retries}: Error uploading chunk {i} of batch {upload_data.batch_pk}: {str(e)}"
                )
                attempt += 1
                if attempt < max_retries:
                    logging.info(f"Retrying upload of chunk {i}")
                    time.sleep(retry_delay)
                else:
                    stop_uploading = True
                    break

        if not success:
            stop_uploading = (
                True  # Stop uploading further chunks if some other error occurs
            )
            break


def upload_files(
    upload_data: UploadData,
    prepared_files: PreparedFiles,
    api_client: UploadAPIClient,
) -> None:
    """Uploads files in chunks and manages the upload process.

    This function first prepares the files for upload, then uploads them in chunks
    using a thread pool executor for concurrent uploads. It finishes by ending the
    upload session.

    Args:
        upload_data (UploadData): An object containing the upload configuration,
            including the batch ID, access token, environment, and file details.
        prepared_files (PreparedFiles): Set of files together with all the metadata needed for upload.
        api_client (UploadAPIClient): Instance of the APIClient class.

    Returns:
        None
    """
    file_status = {}

    # load in prepared files
    file_preparation = prepared_files

    # If prepare_files returned None, log and return
    if file_preparation is None:
        logging.error("Failed to prepare files: no data returned.")
        return

    # handle any errors during preparation
    error_keys = [k for k in file_preparation if "API error occurred" in k]
    if error_keys:
        error_msg_key = error_keys[0]
        logging.error(f"Error preparing files: {file_preparation[error_msg_key]}")
        return

    if "files" not in file_preparation:
        logging.error("Unexpected response from prepare_files: 'files' key missing.")
        return

    # files have been sucessfully prepared, extract the prepared file list
    selected_files = file_preparation["files"]

    # upload the file chunks
    with ThreadPoolExecutor(max_workers=upload_data.max_concurrent_chunks) as executor:
        futures = []
        for file in selected_files:
            future = executor.submit(upload_chunks, upload_data, file, file_status)
            futures.append(future)

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logging.error(f"Error uploading file: {e}")

    # end the upload session
    end_session = api_client.batches_samples_end_upload_session_create(
        upload_data.batch_pk, upload_data.upload_session
    )

    if end_session.status_code != 200:
        logging.error(f"Failed to end upload session for batch {upload_data.batch_pk}.")
    else:
        logging.info(f"All uploads complete.")


def prepare_file(
    resolved_path: Path | None,
    file_metadata: SampleFileMetadata,
    batch_pk: str,
    upload_session: int,
    sample_id: str,
    api_client: UploadAPIClient,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> dict[str, Any]:
    """Prepares a file for uploading by sending metadata to initialize the process.

    Args:
        resolved_path (Path): Resolved path of the file.
        file_metadata (Any): A file object with attributes `name`, `size`, `content_type` and `specimen_oragnism`.
        batch_pk (str): The batch ID associated with the file.
        upload_session (int): The current upload session ID.
        sample_id (str): The ID of the sample that the file will be associated with.
        chunk_size (int): Size of each file chunk in bytes.
        api_client (UploadAPIClient): Instance of the APIClient class.

    Returns:
        dict[str, Any]: File metadata ready for upload or error details.
    """
    if resolved_path is None:
        return {
            "error": "Could not find any read file data for sample",
            "status code": 500,
            "upload_session": upload_session,
        }

    with resolved_path.open("rb") as file:
        file_data = file.read()

    original_file_name = file_metadata["name"]
    total_chunks = math.ceil(sys.getsizeof(file_data) / chunk_size)
    content_type = file_metadata["content_type"]

    form_data = {
        "original_file_name": original_file_name,
        "total_chunks": total_chunks,
        "content_type": content_type,
        "sample_id": sample_id,
    }

    try:
        start_file_upload_response = api_client.batches_uploads_start_file_upload(
            batch_pk=batch_pk, data=form_data
        )
        start_file_upload_json = start_file_upload_response.json()
        if start_file_upload_response.status_code == 200:
            file_ready = {
                "file": file_metadata,
                "upload_id": start_file_upload_json.get("upload_id"),
                "batch_id": batch_pk,
                "sample_id": start_file_upload_json.get("sample_id"),
                "sample_file_id": start_file_upload_json.get("sample_file_id"),
                "total_chunks": total_chunks,
                "upload_session": upload_session,
                "file_data": file_data,
            }
            return file_ready
        else:
            # Include the upload session in the error response
            start_file_upload_json["upload_session"] = upload_session
            return start_file_upload_json
    except APIError as e:
        return {
            "error": str(e),
            "status code": e.status_code,
            "upload_session": upload_session,
        }


@retry(wait=wait_random_exponential(multiplier=2, max=60), stop=stop_after_attempt(10))
def upload_chunk(
    batch_pk: int,
    host: str,
    protocol: str,
    chunk: bytes,
    chunk_index: int,
    upload_id: int,
) -> Response:
    """Upload a single file chunk.

    Args:
        batch_pk (int): ID of sample to upload
        host (str): pathogena host, e.g api.upload-dev.eit-pathogena.com
        protocol (str): protocol, default https
        chunk (bytes): File chunk to be uploaded
        chunk_index (int): Index representing what chunk of the whole
        sample file this chunk is from 0...total_chunks
        upload_id: the id of the upload session

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
                f"{protocol}://{get_upload_host()}/api/v1/batches/{batch_pk}/uploads/upload-chunk/",
                headers={"Authorization": f"Bearer {get_access_token(host)}"},
                files={"chunk": chunk},  # Send the binary chunk
                data={
                    "chunk_index": chunk_index,
                    "upload_id": upload_id,
                },
                follow_redirects=True,
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
            f"Exception while uploading chunk {chunk_index} of batch {batch_pk}: {str(e), chunk[:10]} RESPONSE {response.status_code, response.headers, response.content}"
        )
        raise


def process_queue(chunk_queue: list, max_concurrent_chunks: int) -> Generator[Any]:
    """Processes a queue of chunks concurrently to ensure tno more than 'max_concurrent_chunks' are processed at the same time.

    Args:
        chunk_queue (list): A collection of futures (generated by thread pool executor)
        representing the chunks to be processed.
        max_concurrent_chunks (int): The maximum number of chunks to be processed concurrently.
    """
    if len(chunk_queue) >= max_concurrent_chunks:
        completed = []
        for future in as_completed(chunk_queue):
            yield future.result()
            completed.append(future)
        for future in completed:  # remove completed futures from queue
            chunk_queue.remove(future)


def upload_fastq(
    upload_data: UploadData,
    prepared_files: PreparedFiles,
    api_client: UploadAPIClient,
) -> None:
    """Upload a FASTQ file to the server.

    Args:
        upload_data (UploadData): The upload data including batch_id, session info, etc.
        prepared_files (PreparedFiles): Set of files together with all the metadata needed for upload.
        api_client (UploadAPIClient): Client for connecting to the Upload API.
    """
    upload_files(upload_data, prepared_files, api_client)
