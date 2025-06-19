from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Generic, Literal, Optional, ParamSpec, TypeVar

from pathogena.batch_upload_apis import UploadAPIClient
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


def prepare_sample(sample: UploadSample) -> Sample[PreparedFile]:
    """Prepares a samples' file for upload.

    This function starts the upload session, checks the upload status of the current
    sample and if it has not already been uploaded or partially uploaded prepares
    the sample from scratch.

    Args:
        sample (UploadSample): The upload sample.

    Returns:
        SelectedSample: Prepared sample.
    """
    if sample.is_illumina():
        sample_files = [
            PreparedFile(upload_sample=sample, file_side=1),
            PreparedFile(upload_sample=sample, file_side=2),
        ]
    else:
        sample_files = [PreparedFile(upload_sample=sample, file_side=1)]

    return Sample[PreparedFile](
        instrument_platform=sample.instrument_platform, files=sample_files
    )


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


def start_upload_session(
    batch_pk: str,
    samples: list[UploadSample],
    api_client: UploadAPIClient,
) -> UploadSession:
    """Prepares multiple files for upload.

    This function starts the upload session,
    then starts the upload files for each file
    and returns the bundle.

    Args:
        batch_pk (str): The ID of the batch.
        samples (list[UploadSample]): List of samples to prepare the files for.
        api_client (UploadAPIClient): Instance of the APIClient class.

    Returns:
        UploadSession: Upload session id, name and samples.
    """
    batch_instrument_is_illumina = samples[0].is_illumina()

    prepared_samples: list[Sample[PreparedFile]] = [
        prepare_sample(sample) for sample in samples
    ]

    # Call start upload session endpoint
    upload_session_id, upload_session_name, sample_summaries = (
        api_client.start_upload_session(batch_pk, prepared_samples)
    )

    if batch_instrument_is_illumina:
        # Duplicate the summaries for each half of the files
        per_file_sample_summaries = [
            item for item in sample_summaries for _ in range(2)
        ]
    else:
        per_file_sample_summaries = sample_summaries

    # Call start upload file endpoint for each file
    index = 0
    uploading_samples: list[Sample[UploadingFile]] = []
    for unprepared_sample in prepared_samples:
        for file in unprepared_sample.files:
            uploading_sample_files: list[UploadingFile] = []
            sample_id = per_file_sample_summaries[index].get("sample_id")
            uploading_file = api_client.start_file_upload(
                file, batch_pk, upload_session_id, sample_id
            )
            uploading_sample_files.append(uploading_file)
            index += 1

        uploading_samples.append(
            Sample[UploadingFile](
                unprepared_sample.instrument_platform, uploading_sample_files
            )
        )

    # Return the bundle of start upload session and start file upload responses
    return UploadSession(
        session_id=upload_session_id,
        name=upload_session_name,
        samples=uploading_samples,
    )
