from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Generic, Literal, TypeVar

from pathogena.models import UploadSample
from pathogena.util import PLATFORMS


class PreparedFile:
    """A file which is prepared for upload (pre `start-file-upload` call)."""

    name: str | None
    size: int
    path: Path | None
    control: str
    content_type: str
    specimen_organism: Literal["mycobacteria", "sars-cov-2", ""]
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

    file_id: int
    upload_id: int
    sample_id: str
    batch_id: str
    upload_session_id: int

    prepared_file: PreparedFile
    uploaded_file_name: str
    generated_name: str

    created_at: datetime
    estimated_completion_time: datetime | None
    time_remaining: float | None
    status: Literal["IN_PROGRESS", "COMPLETE", "FAILED"]
    total_chunks: int

    def __init__(
        self,
        file_id: int,
        upload_id: int,
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
