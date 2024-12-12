import json
import logging
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from pathogena import util
from pathogena.batch_upload_apis import APIClient, APIError
from pathogena.util import find_duplicate_entries

ALLOWED_EXTENSIONS = (".fastq", ".fq", ".fastq.gz", ".fq.gz")


def is_valid_file_extension(
    filename: str, allowed_extensions: tuple[str] = ALLOWED_EXTENSIONS
) -> bool:
    """Check if the file has a valid extension.

    Args:
        filename (str): The name of the file.
        allowed_extensions (tuple[str]): A tuple of allowed file extensions.

    Returns:
        bool: True if the file has a valid extension, False otherwise.
    """
    return filename.endswith(allowed_extensions)


class UploadBase(BaseModel):
    """Base model for any uploaded data."""

    batch_name: str = Field(
        default=None, description="Batch name (anonymised prior to upload)"
    )
    instrument_platform: util.PLATFORMS = Field(
        description="Sequencing instrument platform"
    )
    collection_date: date = Field(description="Collection date in yyyy-mm-dd format")
    country: str = Field(
        min_length=3, max_length=3, description="ISO 3166-2 alpha-3 country code"
    )
    subdivision: str = Field(
        default=None, description="ISO 3166-2 principal subdivision"
    )
    district: str = Field(default=None, description="Granular location")
    specimen_organism: Literal["mycobacteria", "sars-cov-2", ""] = Field(
        default="mycobacteria", description="Target specimen organism scientific name"
    )
    host_organism: str = Field(
        default=None, description="Host organism scientific name"
    )
    amplicon_scheme: str | None = Field(
        default=None,
        description="If a batch of SARS-CoV-2 samples, provides the amplicon scheme",
    )


class UploadSample(UploadBase):
    """Model for an uploaded sample's data."""

    sample_name: str = Field(
        min_length=1, description="Sample name (anonymised prior to upload)"
    )
    upload_csv: Path = Field(description="Absolute path of upload CSV file")
    reads_1: Path = Field(description="Relative path of first FASTQ file")
    reads_2: Path = Field(
        description="Relative path of second FASTQ file", default=None
    )
    control: Literal["positive", "negative", ""] = Field(
        description="Control status of sample"
    )
    # Metadata added to a sample prior to upload.
    reads_1_resolved_path: Path = Field(
        description="Resolved path of first FASTQ file", default=None
    )
    reads_2_resolved_path: Path = Field(
        description="Resolved path of second FASTQ file", default=None
    )
    reads_1_dirty_checksum: str = Field(
        description="Checksum of first FASTQ file", default=None
    )
    reads_2_dirty_checksum: str = Field(
        description="Checksum of second FASTQ file", default=None
    )
    reads_1_cleaned_path: Path = Field(
        description="Path of first FASTQ file after decontamination", default=None
    )
    reads_2_cleaned_path: Path = Field(
        description="Path of second FASTQ file after decontamination", default=None
    )
    reads_1_pre_upload_checksum: str = Field(
        description="Checksum of first FASTQ file after decontamination", default=None
    )
    reads_2_pre_upload_checksum: str = Field(
        description="Checksum of second FASTQ file after decontamination", default=None
    )
    reads_1_upload_file: Path = Field(
        description="Path of first FASTQ file to be uploaded", default=None
    )
    reads_2_upload_file: Path = Field(
        description="Path of second FASTQ file to be uploaded", default=None
    )
    reads_in: int = Field(description="Number of reads in FASTQ file", default=0)
    reads_out: int = Field(
        description="Number of reads in FASTQ file after decontamination", default=0
    )
    reads_removed: int = Field(
        description="Number of reads removed during decontamination", default=0
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @model_validator(mode="after")
    def validate_fastq_files(self):
        """Validate the FASTQ files.

        Returns:
            Self: The validated UploadSample instance.

        Raises:
            ValueError: If any validation checks fail.
        """
        self.reads_1_resolved_path = self.upload_csv.resolve().parent / self.reads_1
        self.reads_2_resolved_path = self.upload_csv.resolve().parent / self.reads_2
        self.check_fastq_paths_are_different()
        fastq_paths = [self.reads_1_resolved_path]
        if self.is_ont():
            if self.reads_2_resolved_path.is_file():
                raise ValueError(
                    f"reads_2 must not be set to a file where instrument_platform is ont ({self.sample_name})"
                )
        elif self.is_illumina():
            fastq_paths.append(self.reads_2_resolved_path)
        for count, file_path in enumerate(fastq_paths, start=1):
            if not file_path.is_file():
                raise ValueError(
                    f"reads_{count} is not a valid file path: {file_path}, does it exist?"
                )
            if file_path.stat().st_size == 0:
                raise ValueError(f"reads_{count} is empty in sample {self.sample_name}")
            if file_path and not is_valid_file_extension(file_path.name):
                raise ValueError(
                    f"Invalid file extension for {file_path.name}. Allowed extensions are {ALLOWED_EXTENSIONS}"
                )
        return self

    @property
    def file1_size(self):
        """Get the size of the first reads file in bytes.

        Returns:
            int: The size of the second file associated with sample.

        """
        return self.reads_1_resolved_path.stat().st_size

    @property
    def file2_size(self):
        """Get the size of the second reads file in bytes.

        Returns:
            int: The size of the second file associated with sample (illumina only).

        """
        return self.reads_2_resolved_path.stat().st_size

    def check_fastq_paths_are_different(self):
        """Check that the FASTQ paths are different.

        Returns:
            Self: The UploadSample instance.

        Raises:
            ValueError: If the FASTQ paths are the same.
        """
        if self.reads_1 == self.reads_2:
            raise ValueError(
                f"reads_1 and reads_2 paths must be different in sample {self.sample_name}"
            )
        return self

    def validate_reads_from_fastq(self) -> None:
        """Validate the reads from the FASTQ files.

        Raises:
            ValueError: If any validation checks fail.
        """
        reads = self.get_read_paths()
        logging.info("Performing FastQ checks and gathering total reads")
        valid_lines_per_read = 4
        self.reads_in = 0
        for read in reads:
            logging.info(f"Calculating read count in: {read}")
            if read.suffix == ".gz":
                line_count = util.reads_lines_from_gzip(file_path=read)
            else:
                line_count = util.reads_lines_from_fastq(file_path=read)
            if line_count % valid_lines_per_read != 0:
                raise ValueError(
                    f"FASTQ file {read.name} does not have a multiple of 4 lines"
                )
            self.reads_in += line_count / valid_lines_per_read
        logging.info(f"{self.reads_in} reads in FASTQ file")

    def get_read_paths(self) -> list[Path]:
        """Get the paths of the read files.

        Returns:
            list[Path]: A list of paths to the read files.
        """
        reads = [self.reads_1_resolved_path]
        if self.is_illumina():
            reads.append(self.reads_2_resolved_path)
        return reads

    def is_ont(self) -> bool:
        """Check if the instrument platform is ONT.

        Returns:
            bool: True if the instrument platform is ONT, False otherwise.
        """
        return self.instrument_platform == "ont"

    def is_illumina(self) -> bool:
        """Check if the instrument platform is Illumina.

        Returns:
            bool: True if the instrument platform is Illumina, False otherwise.
        """
        return self.instrument_platform == "illumina"


class UploadBatch(BaseModel):
    """Model for a batch of upload samples."""

    samples: list[UploadSample]
    skip_reading_fastqs: bool = Field(
        description="Skip checking FastQ files", default=False
    )
    ran_through_hostile: bool = False
    instrument_platform: str = None
    amplicon_scheme: Optional[str] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @model_validator(mode="after")
    def validate_unique_sample_names(self):
        """Validate that sample names are unique.

        Returns:
            Self: The validated UploadBatch instance.

        Raises:
            ValueError: If duplicate sample names are found.
        """
        names = [sample.sample_name for sample in self.samples]
        if len(names) != len(set(names)):
            duplicates = find_duplicate_entries(names)
            raise ValueError(f"Found duplicate sample names: {', '.join(duplicates)}")
        return self

    @model_validator(mode="after")
    def validate_unique_file_names(self):
        """Validate that file names are unique.

        Returns:
            Self: The validated UploadBatch instance.

        Raises:
            ValueError: If duplicate file names are found.
        """
        reads = []
        reads.append([str(sample.reads_1.name) for sample in self.samples])
        if self.is_illumina():
            reads.append([str(sample.reads_2.name) for sample in self.samples])
        for count, reads_list in enumerate(reads, start=1):
            if len(reads_list) > 0 and len(reads_list) != len(set(reads_list)):
                duplicates = find_duplicate_entries(reads_list)
                raise ValueError(
                    f"Found duplicate FASTQ filenames in reads_{count}: {', '.join(duplicates)}"
                )
        return self

    @model_validator(mode="after")
    def validate_single_instrument_platform(self):
        """Validate that all samples have the same instrument platform.

        Returns:
            Self: The validated UploadBatch instance.

        Raises:
            ValueError: If multiple instrument platforms are found.
        """
        instrument_platforms = [sample.instrument_platform for sample in self.samples]
        if len(set(instrument_platforms)) != 1:
            raise ValueError(
                "Samples within a batch must have the same instrument_platform"
            )
        self.instrument_platform = instrument_platforms[0]
        logging.debug(f"{self.instrument_platform=}")
        return self

    @model_validator(mode="after")
    def validate_single_amplicon_scheme(self):
        """Validate that all samples have the same amplicon scheme, or no amplicon scheme.

        Returns:
            Self: The validated UploadBatch instance.

        Raises:
            ValueError: If multiple amplicon schemes are found.
        """
        amplicon_schemes = [sample.amplicon_scheme for sample in self.samples]
        if len(set(amplicon_schemes)) != 1:
            raise ValueError(
                "Samples within a batch must have the same amplicon_scheme"
            )
        self.amplicon_scheme = amplicon_schemes[0]
        logging.debug(f"{self.amplicon_scheme=}")
        return self

    @model_validator(mode="after")
    def validate_no_amplicon_scheme_myco(self):
        """Validate that if the mycobacteria is the specimen organism, amplicon scheme is not specified.

        Returns:
            Self: The validated UploadBatch instance.

        Raises:
            ValueError: If amplicon schemes are found when specimen organism is mycobacteria.
        """
        amplicon_schemes = [sample.amplicon_scheme for sample in self.samples]
        specimen_organisms = [sample.specimen_organism for sample in self.samples]

        if (
            not all(scheme is None for scheme in amplicon_schemes)
            and "mycobacteria" in specimen_organisms
        ):
            raise ValueError(
                "amplicon_scheme must not and cannot be specified for mycobacteria"
            )
        return self

    def update_sample_metadata(self, metadata: dict[str, Any] = None) -> None:
        """Updates the sample metadata.

        Update sample metadata with output from decontamination process, or defaults if
        decontamination is skipped

        Args:
            metadata (dict[str, Any], optional): Metadata to update. Defaults to None.
        """
        if metadata is None:
            metadata = {}
        for sample in self.samples:
            cleaned_sample_data = metadata.get(sample.sample_name, {})
            sample.reads_in = cleaned_sample_data.get("reads_in", sample.reads_in)
            sample.reads_out = cleaned_sample_data.get(
                "reads_out", sample.reads_in
            )  # Assume no change in default
            sample.reads_1_dirty_checksum = util.hash_file(sample.reads_1_resolved_path)
            if self.ran_through_hostile:
                sample.reads_1_cleaned_path = Path(
                    cleaned_sample_data.get("fastq1_out_path")
                )
                sample.reads_1_pre_upload_checksum = util.hash_file(
                    sample.reads_1_cleaned_path
                )
            else:
                sample.reads_1_pre_upload_checksum = sample.reads_1_dirty_checksum
            if sample.is_illumina():
                sample.reads_2_dirty_checksum = util.hash_file(
                    sample.reads_2_resolved_path
                )
                if self.ran_through_hostile:
                    sample.reads_2_cleaned_path = Path(
                        cleaned_sample_data.get("fastq2_out_path")
                    )
                    sample.reads_2_pre_upload_checksum = util.hash_file(
                        sample.reads_2_cleaned_path
                    )
                else:
                    sample.reads_2_pre_upload_checksum = sample.reads_2_dirty_checksum

    def validate_all_sample_fastqs(self) -> None:
        """Validate all sample FASTQ files."""
        for sample in self.samples:
            if not self.skip_reading_fastqs and sample.reads_in == 0:
                sample.validate_reads_from_fastq()
            else:
                logging.warning(
                    f"Skipping additional FastQ file checks as requested (skip_checks = {self.skip_reading_fastqs}"
                )

    def is_ont(self) -> bool:
        """Check if the instrument platform is ONT.

        Returns:
            bool: True if the instrument platform is ONT, False otherwise.
        """
        return self.instrument_platform == "ont"

    def is_illumina(self) -> bool:
        """Check if the instrument platform is Illumina.

        Returns:
            bool: True if the instrument platform is Illumina, False otherwise.
        """
        return self.instrument_platform == "illumina"


class RemoteFile(BaseModel):
    """Model for a remote file."""

    filename: str
    run_id: int
    sample_id: str


def create_batch_from_csv(upload_csv: Path, skip_checks: bool = False) -> UploadBatch:
    """Create an UploadBatch instance from a CSV file.

    Args:
        upload_csv (Path): Path to the upload CSV file.
        skip_checks (bool, optional): Whether to skip FASTQ file checks. Defaults to False.

    Returns:
        UploadBatch: The created UploadBatch instance.
    """
    records = util.parse_csv(upload_csv)
    return UploadBatch(  # Include upload_csv to enable relative fastq path validation
        samples=[UploadSample(**r, **{"upload_csv": upload_csv}) for r in records],
        skip_reading_fastqs=skip_checks,
    )


# below moved from util to avoid circular dependancies
class SelectedFile(TypedDict):
    file: dict[str, str]
    upload_id: int
    # batch_id: int
    batch_pk: int
    sample_id: int
    total_chunks: int
    estimated_completion_time: int
    time_remaining: int
    uploadSession: int
    file_data: Any
    total_chunks: int


class PreparedFiles(TypedDict):
    files: list[SelectedFile]
    uploadSession: int
    uploadSessionData: dict[str, Any]


class UploadFileType:
    """A class representing the parameters related to uploading files."""

    def __init__(
        self,
        access_token,
        batch_pk,
        env,
        # files=list[SelectedFilesType],
        samples: list[UploadSample],
        on_complete: Callable[[util.OnComplete], None] | None = None,
        on_progress: Callable[[util.OnProgress], None] | None = None,
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
        # self.files = files
        self.samples = samples
        self.on_complete = on_complete
        self.on_progress = on_progress
        self.max_concurrent_chunks = max_concurrent_chunks
        self.max_concurrent_files = max_concurrent_files
        self.upload_session = upload_session
        self.abort_controller = abort_controller


@no_type_check
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
    for sample in files:
        samples = []
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
        return {
            "API error occurred": f"Error checking credits: {str(e)}",
            "status code": e.status_code,
        }

    if not check_credits.get("data", {}).get("upload_session"):
        # Log if the upload session could not be resumed
        logging.error("Upload session cannot be resumed. Please create a new batch.")
        return {"API error occurred": "No upload session returned by the API."}

    # Upload session
    upload_session = check_credits["data"]["upload_session"]

    for item in files:
        sample = util.check_if_file_is_in_sample(sample_uploads, item["file"])
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


chunk_size = int(os.getenv("NEXT_PUBLIC_CHUNK_SIZE", 5000000))  # 5000000 = 5 mb


# upload_all chunks of a file
def upload_chunks(
    upload_data: UploadFileType, file: SelectedFile, file_status: dict
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

        util.process_queue(chunk_queue, upload_data.max_concurrent_chunks)

        # chunk the files
        start = i * chunk_size  # 5 MB chunk size default
        end = start + chunk_size
        file_chunk = file["file_data"][start:end]

        # upload chunk
        chunk_upload = util.upload_chunk(
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
                    progress_event = util.OnProgress(
                        upload_id=file["upload_id"],
                        batch_pk=file["batch_pk"],
                        progress=progress,
                        metrics=chunk_upload_result["data"]["metrics"],
                    )
                    upload_data.on_progress(progress_event)

                # If all chunks have been uploaded, complete the file upload

                if chunks_uploaded == file["total_chunks"]:
                    if upload_data.on_complete:
                        complete_event = util.OnComplete(
                            file["upload_id"], file["batch_pk"]
                        )
                        upload_data.on_complete(complete_event)

                    end_status = util.end_upload(file["batch_pk"], file["upload_id"])
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

        for future in util.as_completed(futures):
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
