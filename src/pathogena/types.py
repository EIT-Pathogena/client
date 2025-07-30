from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Generic, Literal, TypedDict, TypeVar

from pathogena.constants import PLATFORMS
from pathogena.models import UploadSample


class PreparedFile:
    """A file which is prepared for upload (pre `start-file-upload` call)."""

    name: str | None
    size: int
    path: Path | None
    control: str
    content_type: str
    specimen_organism: Literal["mycobacteria", "sars-cov-2", "influenza-a", ""]
    data: bytes

    def __init__(self, upload_sample: UploadSample, file_side: Literal[1, 2]):
        if file_side == 1:
            path = upload_sample.reads_1_resolved_path
            size = upload_sample.file1_size
            data = upload_sample.read_file1_data()
        elif file_side == 2:
            path = upload_sample.reads_2_resolved_path
            size = upload_sample.file2_size
            data = upload_sample.read_file2_data()

        self.name = path.name if path else None
        self.size = size
        self.data = data
        self.path = path
        self.control = upload_sample.control.upper()
        self.content_type = (
            "application/gzip"
            if path is not None and path.suffix in ("gzip", "gz")
            else "text/plain"
        )
        self.specimen_organism = upload_sample.specimen_organism


@dataclass
class UploadingFile:
    """A file which is being uploaded (post `start-file-upload` call)."""

    id: int
    upload_id: str
    sample_id: str
    batch_id: str
    upload_session_id: int

    prepared_file: PreparedFile

    status: Literal["IN_PROGRESS", "COMPLETE", "FAILED"]
    total_chunks: int

    def __init__(
        self,
        file_id: int,
        upload_id: str,
        sample_id: str,
        batch_id: str,
        upload_session_id: int,
        total_chunks: int,
        prepared_file: PreparedFile,
        status="IN_PROGRESS",
    ):
        self.id = file_id
        self.upload_id = upload_id
        self.sample_id = sample_id
        self.batch_id = batch_id

        self.prepared_file = prepared_file
        self.total_chunks = total_chunks
        self.upload_session_id = upload_session_id
        self.status = status


FileType = TypeVar("FileType")


@dataclass
class Sample(Generic[FileType]):
    """A TypedDict representing a sample.

    Args:
        instrument_platform: the instrument used to create the sample files (illumina | ont)
        files: list of files in the sample
    """

    instrument_platform: PLATFORMS
    files: list[FileType]


@dataclass
class UploadSession:
    """All the information for an UploadSession.

    Including the response data from
    - `start-upload-session`

    And the per-file-calls to
    - `start-file-upload`

    """

    session_id: int
    name: str
    samples: list[Sample[UploadingFile]]


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
        upload_id: Unique identifier for this upload session -- check this comment
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
        upload_id (str): The ID of the uploading file.
        batch_pk (int): The batch ID associated with the file upload.
        progress (float): The percentage of upload completion.
        metrics (UploadMetrics): The metrics associated with the upload.
    """

    upload_id: str
    batch_pk: int
    progress: float
    metrics: UploadMetrics


@dataclass
class OnComplete:
    """Initializes the OnComplete instance.

    Args:
        upload_id (str): The ID of the uploading file.
        batch_pk (int): The batch ID associated with the file upload.
    """

    upload_id: str
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
