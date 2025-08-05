import logging
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from gpas import __version__, util
from gpas.util import find_duplicate_entries

ALLOWED_EXTENSIONS = (".fastq", ".fq", ".fastq.gz", ".fq.gz")


def is_valid_file_extension(
    filename: str,
    allowed_extensions: tuple[
        Literal[".fastq"], Literal[".fq"], Literal[".fastq.gz"], Literal[".fq.gz"]
    ] = ALLOWED_EXTENSIONS,
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

    batch_name: str | None = Field(
        default=None, description="Batch name (anonymised prior to upload)"
    )
    instrument_platform: util.PLATFORMS = Field(
        description="Sequencing instrument platform"
    )
    collection_date: date = Field(description="Collection date in yyyy-mm-dd format")
    country: str = Field(
        min_length=3, max_length=3, description="ISO 3166-2 alpha-3 country code"
    )
    subdivision: str | None = Field(
        default=None, description="ISO 3166-2 principal subdivision"
    )
    district: str = Field(default=None, description="Granular location")
    specimen_organism: Literal["mycobacteria", "sars-cov-2"] = Field(
        default="mycobacteria", description="Target specimen organism scientific name"
    )
    host_organism: str | None = Field(
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
    reads_2: Path | None = Field(
        description="Relative path of second FASTQ file", default=None
    )
    control: Literal["positive", "negative", ""] = Field(
        description="Control status of sample"
    )
    # Metadata added to a sample prior to upload.
    reads_1_resolved_path: Path | None = Field(
        description="Resolved path of first FASTQ file", default=None
    )
    reads_2_resolved_path: Path | None = Field(
        description="Resolved path of second FASTQ file", default=None
    )
    reads_1_dirty_checksum: str | None = Field(
        description="Checksum of first FASTQ file", default=None
    )
    reads_2_dirty_checksum: str | None = Field(
        description="Checksum of second FASTQ file", default=None
    )
    reads_1_cleaned_path: Path | None = Field(
        description="Path of first FASTQ file after decontamination", default=None
    )
    reads_2_cleaned_path: Path | None = Field(
        description="Path of second FASTQ file after decontamination", default=None
    )
    reads_1_pre_upload_checksum: str | None = Field(
        description="Checksum of first FASTQ file after decontamination", default=None
    )
    reads_2_pre_upload_checksum: str | None = Field(
        description="Checksum of second FASTQ file after decontamination", default=None
    )
    reads_1_upload_file: Path | None = Field(
        description="Path of first FASTQ file to be uploaded", default=None
    )
    reads_2_upload_file: Path | None = Field(
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
        if self.reads_2 is not None:
            self.reads_2_resolved_path = self.upload_csv.resolve().parent / self.reads_2
        else:
            self.reads_2_resolved_path = None
        self.check_fastq_paths_are_different()
        fastq_paths = [self.reads_1_resolved_path]
        if self.is_ont():
            if (
                self.reads_2_resolved_path is not None
                and self.reads_2_resolved_path.is_file()
            ):
                raise ValueError(
                    f"reads_2 must not be set to a file where instrument_platform is ont ({self.sample_name})"
                )
        elif self.is_illumina() and self.reads_2_resolved_path is not None:
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
    def file1_size(self) -> int:
        """Get the size of the first reads file in bytes.

        Returns:
            int: The size of the second file associated with sample.

        """
        return (
            self.reads_1_resolved_path.stat().st_size
            if self.reads_1_resolved_path
            else 0
        )

    @property
    def file2_size(self):
        """Get the size of the second reads file in bytes.

        Returns:
            int: The size of the second file associated with sample (illumina only).

        """
        return (
            self.reads_2_resolved_path.stat().st_size
            if self.reads_2_resolved_path
            else 0
        )

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
            self.reads_in += int(line_count / valid_lines_per_read)
        logging.info(f"{self.reads_in} reads in FASTQ file")

    def get_read_paths(self) -> list[Path]:
        """Get the paths of the read files.

        Returns:
            list[Path]: A list of paths to the read files.
        """
        match (self.reads_1_resolved_path, self.reads_2_resolved_path):
            case None, None:
                return []
            case x, None:
                return [x]
            case None, x:
                return [x]
            case x, y if self.is_illumina():
                return [x, y]
            case x, y if self.is_ont():  # ont only one file
                return [x]
            case _:
                return []

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
    instrument_platform: str | None = None
    amplicon_scheme: str | None = None
    specimen_organism: str | None = None

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
            reads.append(
                [str(sample.reads_2.name) for sample in self.samples if sample.reads_2]
            )
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

            if sample.reads_1_resolved_path is not None:
                sample.reads_1_dirty_checksum = util.hash_file(
                    sample.reads_1_resolved_path
                )
            else:
                sample.reads_1_dirty_checksum = ""
            if self.ran_through_hostile:
                sample.reads_1_cleaned_path = Path(
                    cleaned_sample_data.get("fastq1_out_path")
                )
                sample.reads_1_pre_upload_checksum = util.hash_file(
                    sample.reads_1_cleaned_path
                )
            else:
                sample.reads_1_pre_upload_checksum = sample.reads_1_dirty_checksum
            if sample.is_illumina() and sample.reads_2_resolved_path:
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
    samples = [UploadSample(**r, **{"upload_csv": upload_csv}) for r in records]
    specimen_organism = samples[0].specimen_organism if len(samples) > 0 else None

    return UploadBatch(  # Include upload_csv to enable relative fastq path validation
        samples=samples,
        skip_reading_fastqs=skip_checks,
        specimen_organism=specimen_organism,
    )
