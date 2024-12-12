import json
import logging
import math
import os
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, TypedDict

import httpx
from httpx import Response, codes
from tenacity import retry, stop_after_attempt, wait_random_exponential

from pathogena.batch_upload_apis import APIClient, APIError
from pathogena.constants import DEFAULT_CHUNK_SIZE, DEFAULT_UPLOAD_HOST
from pathogena.log_utils import httpx_hooks
from pathogena.models import UploadSample
from pathogena.util import get_access_token


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

class SampleUploadStatus(TypedDict):
    """A TypedDict representing the status and metadata of a sample upload.

    Args:
        id: Unique identifier for the sample upload
        batch: ID of the batch this sample belongs to
        file_path: Path to the uploaded file on the server
        uploaded_file_name: Original name of the uploaded file
        generated_name: System-generated name for the file
        created_at: Timestamp when the upload was created
        upload_status: Current status of the upload (IN_PROGRESS/COMPLETE/FAILED)
        total_chunks: Total number of chunks for this file
        upload_id: Unique identifier for this upload session
        legacy_sample_id: Original sample ID from legacy system
        hyphenated_legacy_sample_id: Hyphenated version of legacy sample ID
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
    hyphenated_legacy_sample_id: str
    metrics: UploadMetrics

class BatchUploadStatus(TypedDict):
    """A TypedDict representing the status of a batch upload and its samples.

    Args:
        upload_status: Current status of the batch upload (e.g. "in_progress", "complete")
        samples: Dictionary mapping sample IDs to their individual upload statuses
    """
    upload_status: str
    samples: dict[str, SampleUploadStatus]


class SelectedFile(TypedDict):
    """A TypedDict representing a file selected for upload with its metadata.

    Args:
        file: Dictionary containing file information with string keys and values
        upload_id: Unique identifier for the upload
        batch_pk: Primary key of the batch this file belongs to
        sample_id: Identifier for the sample associated with this file
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
    sample_id: int
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
        metrics (Metrics): The metrics associated with the upload.
    """

    upload_id: int
    batch_pk: int
    progress: float
    metrics: Metrics


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
class UploadFileType:
    """A class representing the parameters related to uploading files."""

    def __init__(
        self,
        access_token,
        batch_pk,
        env,
        samples: list[UploadSample],
        on_complete: Callable[[OnComplete], None] | None = None,
        on_progress: Callable[[OnProgress], None] | None = None,
        max_concurrent_chunks: int = 5,
        max_concurrent_files: int = 3,
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
    for sample_data in samples.values():
        if sample_data.get("uploaded_file_name") == file.get("name"):
            return sample_data

    return False


def prepare_files(
    batch_pk: int,
    instrument_code: str,
    files: list[UploadSample],
    api_client: APIClient,
    sample_uploads: dict[str, Any] | None = None,
) -> PreparedFiles:
    """Prepares multiple files for upload by checking credits, resuming sessions, and validating file states.

    Args:
        batch_pk (int): The ID of the batch.
        instrument_code (str): The instrument code.
        files (list[UploadSample]): List of files to prepare.
        sample_uploads (dict[str, Any] | None): State of sample uploads, if available.
        api_client (APIClient): Instance of the APIClient class.

    Returns:
        PreparedFiles: Prepared file metadata, upload session information, and session data.
    """
    selected_files = []

    ## check if we have enough credits to upload the files
    samples = []
    for sample in files:
        if sample.is_illumina():
            samples.append(
                {
                    "name": sample.sample_name,
                    "size": sample.file1_size,
                    "control": sample.control,
                }
            )
            samples.append(
                {
                    "name": sample.sample_name,
                    "size": sample.file2_size,
                    "control": sample.control,
                }
            )
        else:
            samples.append(
                {
                    "name": sample.sample_name,
                    "size": sample.file1_size,
                    "control": sample.control,
                }
            )

    batch_credit_form = {
        "samples": json.dumps(samples),
        "instrument": instrument_code,
    }
    try:
        # check credits and start upload session
        check_credits = api_client.batches_samples_start_upload_session_create(
            batch_pk=batch_pk, data=batch_credit_form
        )
    except APIError as e:
        raise APIError(
            f"Error checking credits: {str(e)}",
            e.status_code,
        ) from e

    if not check_credits.get("data", {}).get("upload_session"):
        # Log if the upload session could not be resumed
        logging.exception(
            "Upload session cannot be resumed. Please create a new batch."
        )
        raise APIError(
            "No upload session returned by the API.", codes.INTERNAL_SERVER_ERROR
        )

    # Upload session
    upload_session = check_credits["data"]["upload_session"]

    item: UploadSample
    for item in files:
        sample = check_if_file_is_in_sample(sample_uploads, item.file)
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
            file_ready = util.prepare_file(
                item["file"], batch_pk, upload_session, api_client
            )
            if file_ready:
                selected_files.append(file_ready)

    return {
        "files": selected_files,
        "uploadSession": upload_session,
        "uploadSessionData": check_credits["data"],
    }


# upload_all chunks of a file
def upload_chunks(
    upload_data: UploadFileType,
    file: SelectedFile,
    file_status: dict,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> None:
    """Uploads chunks of a single file.

    Args:
        upload_data (UploadFileType): The upload data including batch_id, session info, etc.
        file (SelectedFile): The file to upload (with file data, total chunks, etc.)
        file_status (dict): The dictionary to track the file upload progress.

    Returns:
        None: This function does not return anything, but updates the `file_status` dictionary
            and calls the provided `on_progress` and `on_complete` callback functions.
    """
    chunks_uploaded = 0
    chunk_queue = []
    stop_uploading = False

    for i in range(file["total_chunks"]):  # total chunks = file.size/chunk_size
        # stop uploading chunks if one returns a 400 error
        if stop_uploading:
            break

        process_queue(chunk_queue, upload_data.max_concurrent_chunks)

        # chunk the files
        start = i * chunk_size  # 5 MB chunk size default
        end = start + chunk_size
        file_chunk = file["file_data"][start:end]

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
            chunk_upload_result = chunk_upload.json()

            # stop uploading subsequent chunks if upload chunk retuns a 400
            if chunk_upload_result.status_code == 400:
                logging.error(
                    f"Chunk upload failed for chunk {i} of batch {upload_data.batch_pk}. Response: {chunk_upload_result.text}"
                )
                stop_uploading = True
                break

            # process result of chunk upload for upload chunks that don't return 400 status
            # if chunk_upload and "data" in chunk_upload_result and "metrics" in chunk_upload_result["data"]:
            if chunk_upload and chunk_upload_result["data"]["metrics"]:
                chunks_uploaded += 1
                file_status[file["upload_id"]] = {
                    "chunks_uploaded": chunks_uploaded,
                    "total_chunks": file["total_chunks"],
                    "metrics": chunk_upload_result["data"]["metrics"],
                }
                progress = (chunks_uploaded / file["total_chunks"]) * 100
                # Create an OnProgress instance
                if upload_data.on_progress:
                    progress_event = OnProgress(
                        upload_id=file["upload_id"],
                        batch_pk=file["batch_pk"],
                        progress=progress,
                        metrics=chunk_upload_result["data"]["metrics"],
                    )
                    upload_data.on_progress(progress_event)

                # If all chunks have been uploaded, complete the file upload

                if chunks_uploaded == file["total_chunks"]:
                    if upload_data.on_complete:
                        complete_event = OnComplete(file["upload_id"], file["batch_pk"])
                        upload_data.on_complete(complete_event)

                    end_status = end_upload(file["batch_pk"], file["upload_id"])
                    if end_status["status"] == 400:
                        logging.error(
                            f"Failed to end upload for file: {file['upload_id']} (Batch ID: {file['batch_pk']})"
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
        files=upload_data.samples,
        api_client=api_client,
        sample_uploads=sample_uploads,
    )

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
    logging.info(f"upload_files, {file_preparation['files']}")
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
    end_session = APIClient.batches_samples_end_upload_session_create(
        upload_data.batch_pk, upload_data.batch_pk
    )

    if end_session["status"] != 200:
        logging.error(f"Failed to end upload session for batch {upload_data.batch_pk}.")
    else:
        logging.info(f"All uploads complete.")


def prepare_file(
    file: Any,
    batch_pk: int,
    upload_session: int,
    api_client: APIClient,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
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


def process_queue(chunk_queue: list, max_concurrent_chunks: int) -> Generator[Any]:
    """Processes a queue of chunks concurrently to ensure tno more than 'max_concurrent_chunks' are processed at the same time.

    Args:
        chunk_queue (list): A collection of futures (generated by thread pool executor)
        representing the chunks to be processed.
        max_concurrent_chunks (int): The maximum number of chunks to be processed concurrently.
    """
    if len(chunk_queue) >= max_concurrent_chunks:
        for future in as_completed(chunk_queue):
            yield future.result()


def end_upload(batch_pk: int, file_id: int) -> dict[str, Any]:
    """End the upload of a sample.

    Args:
        batch_pk (int):ID of the uploaded sample.
        upload_session (int): ID of the upload session.

    Returns:
        dict[str, Any]: The response JSON from the API.
    """
    data = {"upload_id": file_id}
    api_client = APIClient()

    return api_client.batches_uploads_end_create(batch_pk, data)


def end_upload_session(batch_pk: int, upload_session: int) -> dict[str, Any]:
    """End the upload session.

    Args:
        batch_pk (int):ID of the uploaded sample.
        upload_session (int): ID of the upload session.

    Returns:
        dict[str, Any]: The response JSON from the API.
    """
    api_client = APIClient()

    return api_client.batches_samples_end_upload_session_create(
        batch_pk, upload_session
    )


def upload_fastq(
    # batch_pk: int,
    # sample_name: str,
    # reads: Path,
    upload_data: UploadFileType,
    instrument_code: str,
    api_client: APIClient,
    sample_uploads: dict[str, Any] | None = None,
) -> None:
    """Upload a FASTQ file to the server.

    Args:
        batch_pk (int): The ID of the sample.
        sample_name (str): The name of the sample.
        reads (Path): The path to the FASTQ file.
        upload_data (UploadFileType): The upload data including batch_id, session info, etc.
        instrument_code (str): The instument code used to take sample.
    """
    # reads = Path(reads)
    # logging.debug(f"upload_fastq(): {upload_data.batch_pk=}, {sample_name=}, {reads=}")
    # logging.info(f"Uploading {sample_name}")
    # checksum = hash_file(reads)
    upload_files(upload_data, instrument_code, api_client, sample_uploads)
    # logging.info(f"  Uploaded {reads.name}")


# from pathogena import prepare_files
# from pathogena.models import UploadSample
# from pathogena.models import prepare_files

# class SelectedFile(TypedDict):
#     file: dict[str, str]
#     upload_id: int
#     # batch_id: int
#     batch_pk: int
#     sample_id: int
#     total_chunks: int
#     estimated_completion_time: int
#     time_remaining: int
#     uploadSession: int
#     file_data: Any
#     total_chunks: int


# class PreparedFiles(TypedDict):
#     files: list[SelectedFile]
#     uploadSession: int
#     uploadSessionData: dict[str, Any]


# class SelectedFilesType:
#     """Class representing a selected file for upload."""

#     def __init__(self, upload_id, batch_pk, file_data, total_chunks, upload_session):
#         """Initializes a SelectedFilesType instance.

#         Args:
#             upload_id (str): The ID of the upload.
#             batch_pk (int): The batch ID associated with the file.
#             file_data (Any): The file data object.
#             total_chunks (int): The total number of chunks to divide the file into.
#             upload_session (int): The upload session ID.
#         """
#         self.upload_id = upload_id
#         self.batch_pk = batch_pk
#         self.file_data = file_data
#         self.total_chunks = total_chunks
#         self.upload_session = upload_session


# class UploadFileType:
#     """A class representing the parameters related to uploading files."""

#     def __init__(
#         self,
#         access_token,
#         batch_pk,
#         env,
#         # files=list[SelectedFilesType],
#         samples: list[UploadSample],
#         on_complete: Callable[[OnComplete], None] | None = None,
#         on_progress: Callable[[OnProgress], None] | None = None,
#         max_concurrent_chunks: int = 5,
#         max_concurrent_files: int = 3,
#         upload_session=None,
#         abort_controller=None,
#     ):
#         """Initializes the UploadFileType instance.

#         Args:
#             access_token (str): The access token for authentication.
#             batch_pk (int): The batch ID for the upload.
#             env (str): The environment for the upload endpoint.
#             files (list[SelectedFilesType]): A list of selected files to upload. Defaults to an empty list.
#             on_complete (Callable[[OnComplete], None]): A callback function to call when the upload is complete.
#             on_progress (Callable[[OnProgress], None]): A callback function to call during the upload progress.
#             max_concurrent_chunks (int): The maximum number of chunks to upload concurrently. Defaults to 5.
#             max_concurrent_files (int): The maximum number of files to upload concurrently. Defaults to 3.
#             upload_session (int | None): The upload session ID.
#             abort_controller (Any | None): An optional controller to abort the upload.
#         """
#         self.access_token = access_token
#         self.batch_pk = batch_pk
#         self.env = env
#         # self.files = files
#         self.samples = samples
#         self.on_complete = on_complete
#         self.on_progress = on_progress
#         self.max_concurrent_chunks = max_concurrent_chunks
#         self.max_concurrent_files = max_concurrent_files
#         self.upload_session = upload_session
#         self.abort_controller = abort_controller

# @no_type_check
# def prepare_files(
#     batch_pk: int,
#     instrument_code: str,
#     files: list[UploadSample],
#     api_client: APIClient,
#     sample_uploads: dict[str, Any] | None = None,
# ) -> PreparedFiles:
#     """Prepares multiple files for upload by checking credits, resuming sessions, and validating file states.

#     Args:
#         batch_pk (int): The ID of the batch.
#         instrument_code (str): The instrument code.
#         files (list[UploadSample]): List of files to prepare.
#         sample_uploads (dict[str, Any] | None): State of sample uploads, if available.
#         api_client (APIClient): Instance of the APIClient class.

#     Returns:
#         PreparedFiles: Prepared file metadata, upload session information, and session data.
#     """
#     selected_files = []

#     ## check if we have enough credits to upload the files
#     for sample in files:
#         samples = []
#         if sample.is_illumina():
#             samples.append(
#                 {
#                     "name": sample.name,
#                     "size": sample.file1_size,
#                     "control": sample.control,
#                 }
#             )
#             samples.append(
#                 {
#                     "name": sample.name,
#                     "size": sample.file2_size,
#                     "control": sample.control,
#                 }
#             )
#         else:
#             samples.append(
#                 {
#                     "name": sample.name,
#                     "size": sample.file1_size,
#                     "control": sample.control,
#                 }
#             )

#     batch_credit_form = {
#         "samples": json.dumps(samples),
#         "instrument": instrument_code,
#     }
#     try:
#         # check credits and start upload session
#         check_credits = api_client.batches_samples_start_upload_session_create(
#             batch_pk=batch_pk, data=batch_credit_form
#         )
#     except APIError as e:
#         return {
#             "API error occurred when checking credits": str(e),
#             "status code": e.status_code,
#         }

#     if not check_credits.get("data", {}).get("upload_session"):
#         # Log if the upload session could not be resumed
#         logging.error("Upload session cannot be resumed. Please create a new batch.")
#         return

#     # Upload session
#     upload_session = check_credits["data"]["upload_session"]

#     for item in files:
#         sample = check_if_file_is_in_sample(sample_uploads, item["file"])
#         if (
#             sample
#             and sample.get("upload_status") != "COMPLETE"
#             and sample.get("total_chunks", 0) > 0
#         ):
#             # File not already uploaded, add to selected files
#             selected_files.append(
#                 {
#                     "file": item["file"],
#                     "upload_id": sample.get("upload_id"),
#                     "batch_id": batch_pk,
#                     "sample_id": sample.get("id"),
#                     "total_chunks": sample.get("metrics", {}).get(
#                         "chunks_total", sample.get("total_chunks", 0)
#                     ),
#                     "estimated_completion_time": sample.get("metrics", {}).get(
#                         "estimated_completion_time"
#                     ),
#                     "time_remaining": sample.get("metrics", {}).get("time_remaining"),
#                     "uploadSession": upload_session,
#                 }
#             )
#         elif sample and sample.get("upload_status") == "COMPLETE":
#             # Log that the file has already been uploaded, don't add to selected files
#             logging.info(f"File '{item['file']['name']}' has already been uploaded.")
#         else:
#             # Prepare new file and add to selected files
#             file_ready = prepare_file(
#                 item["file"], batch_pk, upload_session, api_client
#             )
#             if file_ready:
#                 selected_files.append(file_ready)

#     return {
#         "files": selected_files,
#         "uploadSession": upload_session,
#         "uploadSessionData": check_credits["data"],
#     }

# # upload_all chunks of a file
# def upload_chunks(
#     upload_data: UploadFileType, file: SelectedFile, file_status: dict
# ) -> None:
#     """Uploads chunks of a single file.

#     Args:
#         upload_data (UploadFileType): The upload data including batch_id, session info, etc.
#         file (SelectedFile): The file to upload (with file data, total chunks, etc.)
#         file_status (dict): The dictionary to track the file upload progress.

#     Returns:
#         None: This function does not return anything, but updates the `file_status` dictionary
#             and calls the provided `on_progress` and `on_complete` callback functions.
#     """
#     chunks_uploaded = 0
#     chunk_queue = []
#     stop_uploading = False

#     for i in range(file["total_chunks"]):  # total chunks = file.size/chunk_size
#         # stop uploading chunks if one returns a 400 error
#         if stop_uploading:
#             break

#         process_queue(chunk_queue, upload_data.max_concurrent_chunks)

#         # chunk the files
#         start = i * chunk_size  # 5 MB chunk size default
#         end = start + chunk_size
#         file_chunk = file["file_data"][start:end]

#         # upload chunk
#         chunk_upload = upload_chunk(
#             batch_pk=upload_data.batch_pk,
#             host=upload_data.env,
#             protocol="https",
#             checksum="checksum",
#             dirty_checksum="dirty_checksum",
#             chunk=file_chunk,
#             chunk_index=i,
#         )
#         chunk_queue.append(chunk_upload)

#         try:
#             # get result of upload chunk
#             chunk_upload_result = chunk_upload.json()

#             # stop uploading subsequent chunks if upload chunk retuns a 400
#             if chunk_upload_result.status_code == 400:
#                 logging.error(
#                     f"Chunk upload failed for chunk {i} of batch {upload_data.batch_pk}. Response: {chunk_upload_result.text}"
#                 )
#                 stop_uploading = True
#                 break

#             # process result of chunk upload for upload chunks that don't return 400 status
#             # if chunk_upload and "data" in chunk_upload_result and "metrics" in chunk_upload_result["data"]:
#             if chunk_upload and chunk_upload_result["data"]["metrics"]:
#                 chunks_uploaded += 1
#                 file_status[file["upload_id"]] = {
#                     "chunks_uploaded": chunks_uploaded,
#                     "total_chunks": file["total_chunks"],
#                     "metrics": chunk_upload_result["data"]["metrics"],
#                 }
#                 progress = (chunks_uploaded / file["total_chunks"]) * 100
#                 # Create an OnProgress instance
#                 if upload_data.on_progress:
#                     progress_event = OnProgress(
#                         upload_id=file["upload_id"],
#                         batch_pk=file["batch_pk"],
#                         progress=progress,
#                         metrics=chunk_upload_result["data"]["metrics"],
#                     )
#                     upload_data.on_progress(progress_event)

#                 # If all chunks have been uploaded, complete the file upload

#                 if chunks_uploaded == file["total_chunks"]:
#                     if upload_data.on_complete:
#                         complete_event = OnComplete(file["upload_id"], file["batch_pk"])
#                         upload_data.on_complete(complete_event)
#                     end_status = end_upload(file["batch_pk"], file["upload_id"])
#                     if end_status["status"] == 400:
#                         logging.error(
#                             f"Failed to end upload for file: {file['upload_id']} (Batch ID: {file['batch_pk']})"
#                         )

#         except Exception as e:
#             logging.error(
#                 f"Error uploading chunk {i} of batch {upload_data.batch_pk}: {str(e)}"
#             )
#             stop_uploading = (
#                 True  # Stop uploading further chunks if some other error occurs
#             )
#             break


# def upload_files(
#     upload_data: UploadFileType,
#     instrument_code: str,
#     api_client: APIClient,
#     sample_uploads: dict[str, Any] | None = None,
# ) -> None:
#     """Uploads files in chunks and manages the upload process.

#     This function first prepares the files for upload, then uploads them in chunks
#     using a thread pool executor for concurrent uploads. It finishes by ending the
#     upload session.

#     Args:
#         upload_data (UploadFileType): An object containing the upload configuration,
#             including the batch ID, access token, environment, and file details.
#         instrument_code (str): The instrument code used to generate the data. This is
#             passed to the backend API for processing.
#         api_client (APIClient): Instance of the APIClient class.
#         sample_uploads (dict[str, Any] | None): State of sample uploads, if available.

#     Returns:
#         None
#     """
#     file_status = {}

#     # prepare files before uploading
#     file_preparation = prepare_files.prepare_files(
#         batch_pk=upload_data.batch_pk,
#         instrument_code=instrument_code,
#         files=upload_data.samples,
#         api_client=api_client,
#         sample_uploads=sample_uploads,
#     )

#     # handle any errors during preparation
#     if "API error occurred" in file_preparation:
#         logging.error(
#             f"Error preparing files: {file_preparation['API error occurred']}"
#         )
#         return file_preparation

#     # files have been sucessfully prepared, extract the prepared file list
#     selected_files = file_preparation["files"]

#     # upload the file chunks
#     with ThreadPoolExecutor(max_workers=upload_data.max_concurrent_chunks) as executor:
#         futures = []
#         for file in selected_files:
#             f = file["file"]
#             future = executor.submit(upload_chunks, upload_data, f, file_status)
#             futures.append(future)

#         for future in as_completed(futures):
#             try:
#                 future.result()
#             except Exception as e:
#                 logging.error(f"Error uploading file: {e}")

#     # end the upload session
#     end_session = APIClient.batches_samples_end_upload_session_create(
#         upload_data.batch_pk, upload_data.batch_pk
#     )

#     if end_session["status"] != 200:
#         logging.error(f"Failed to end upload session for batch {upload_data.batch_pk}.")
#     else:
#         logging.info(f"All uploads complete.")


# def upload_fastq(
#     # batch_pk: int,
#     # sample_name: str,
#     # reads: Path,
#     upload_data: UploadFileType,
#     instrument_code: str,
#     api_client: APIClient,
#     sample_uploads: dict[str, Any] | None = None,
# ) -> None:
#     """Upload a FASTQ file to the server.

#     Args:
#         batch_pk (int): The ID of the sample.
#         sample_name (str): The name of the sample.
#         reads (Path): The path to the FASTQ file.
#         upload_data (UploadFileType): The upload data including batch_id, session info, etc.
#         instrument_code (str): The instument code used to take sample.
#     """
#     # reads = Path(reads)
#     # logging.debug(f"upload_fastq(): {upload_data.batch_pk=}, {sample_name=}, {reads=}")
#     # logging.info(f"Uploading {sample_name}")
#     # checksum = hash_file(reads)
#     upload_files(upload_data, instrument_code, api_client, sample_uploads)
#     # logging.info(f"  Uploaded {reads.name}")
