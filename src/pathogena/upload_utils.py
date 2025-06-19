import logging
import os
import time
from collections.abc import Generator
from concurrent.futures import as_completed
from dataclasses import dataclass
from datetime import datetime
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
from pathogena.upload_session import UploadingFile
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
        control: Whether this is a control sample
        content_type: The content type
        specimen_organism: The organism from which the sample was taken
    """

    name: str
    size: int
    control: str
    content_type: str
    specimen_organism: str


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
        upload_session_id=None,
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
        self.upload_session_id = upload_session_id
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


def check_if_file_is_in_all_sample_files(
    sample_files: dict[str, SampleFileUploadStatus] | None = None,
    file: SampleFileMetadata | None = None,
) -> tuple[bool, SampleFileUploadStatus | dict]:
    """Checks if a given file is already present in the set of files ready for upload.

    Args:
        sample_files (dict[str, SampleFileUploadStatus]): The sample files ready for upload.
        That is, a dictionary where keys are sample file IDs and values are dictionaries containing file data.
        file (UploadSample | None): A dictionary representing the file, expected to have a 'name' key.

    Returns:
        tuple[bool, SampleFileUploadStatus | dict]: A bool if it was found and the result if
            true.
    """
    # Extract samples from sample_uploads, defaulting to an empty dictionary if None
    if not sample_files or not file:
        return (False, {})

    # Iterate through sample IDs and check if the uploaded file name matches the file's name
    for sample_data in sample_files.values():
        if sample_data.get("uploaded_file_name") == file["name"]:
            return (True, sample_data)

    return (False, {})


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


# upload_all chunks of a file
def upload_chunks(
    upload_data: UploadData,
    file: UploadingFile,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> None:
    """Uploads chunks of a single file.

    Args:
        upload_data (UploadData): The upload data including batch_id, session info, etc.
        file (SelectedFile): The file to upload (with file data, total chunks, etc.)
        chunk_size (int): Default size of file chunk to upload (5mb)

    Returns:
        None: This function does not return anything, but calls the provided
            `on_progress` and `on_complete` callback functions.
    """
    chunks_uploaded = 0
    chunk_queue: list[Response] = []
    stop_uploading = False

    max_retries = DEFAULT_MAX_UPLOAD_RETRIES
    retry_delay = DEFAULT_RETRY_DELAY
    for i in range(file.total_chunks):  # total chunks = file.size/chunk_size
        if stop_uploading:
            break

        process_queue(chunk_queue, upload_data.max_concurrent_chunks)

        # chunk the files
        start = i * chunk_size  # 5 MB chunk size default
        end = start + chunk_size
        file_chunk = file.prepared_file.data[start:end]

        success = False
        attempt = 0

        while attempt < max_retries and not success:
            chunk_upload = upload_chunk(
                batch_pk=upload_data.batch_pk,
                host=get_host(),
                protocol=get_protocol(),
                chunk=file_chunk,
                chunk_index=i,
                upload_id=file.upload_id,
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
                    progress = (chunks_uploaded / file.total_chunks) * 100

                    # Create an OnProgress instance
                    progress_event = OnProgress(
                        upload_id=file.upload_id,
                        batch_pk=upload_data.batch_pk,
                        progress=progress,
                        metrics=chunk_upload_result["metrics"],
                    )
                    upload_data.on_progress = progress_event

                    # If all chunks have been uploaded, complete the file upload
                    if chunks_uploaded == file.total_chunks:
                        complete_event = OnComplete(
                            file.upload_id, upload_data.batch_pk
                        )
                        upload_data.on_complete = complete_event
                        client = UploadAPIClient()
                        end_status = client.batches_uploads_end_file_upload(
                            upload_data.batch_pk,
                            data={"upload_id": file.upload_id},
                        )
                        if end_status.status_code == 400:
                            logging.error(
                                f"Failed to end upload for file: {file.upload_id} (Batch ID: {upload_data.batch_pk})"
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
