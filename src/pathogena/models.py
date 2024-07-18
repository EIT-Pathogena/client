import logging
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from pathogena import util
from pathogena.util import find_duplicate_entries

ALLOWED_EXTENSIONS = (".fastq", ".fq", ".fastq.gz", ".fq.gz")


def is_valid_file_extension(
    filename: str, allowed_extensions: tuple[str] = ALLOWED_EXTENSIONS
):
    return filename.endswith(allowed_extensions)


class UploadBase(BaseModel):
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
    specimen_organism: Literal["mycobacteria", ""] = Field(
        default="mycobacteria", description="Target specimen organism scientific name"
    )
    host_organism: str = Field(
        default=None, description="Host organism scientific name"
    )


class UploadSample(UploadBase):
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

    def check_fastq_paths_are_different(self):
        if self.reads_1 == self.reads_2:
            raise ValueError(
                f"reads_1 and reads_2 paths must be different in sample {self.sample_name}"
            )
        return self

    def validate_reads_from_fastq(self):
        reads = self.get_read_paths()
        logging.info("Performing FastQ checks and gathering total reads")
        line_count = 0
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
        return

    def get_read_paths(self):
        reads = [self.reads_1_resolved_path]
        if self.is_illumina():
            reads.append(self.reads_2_resolved_path)
        return reads

    def is_ont(self):
        return self.instrument_platform == "ont"

    def is_illumina(self):
        return self.instrument_platform == "illumina"


class UploadBatch(BaseModel):
    samples: list[UploadSample]
    skip_reading_fastqs: bool = Field(
        description="Skip checking FastQ files", default=False
    )
    ran_through_hostile: bool = False
    instrument_platform: str = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @model_validator(mode="after")
    def validate_unique_sample_names(self):
        names = [sample.sample_name for sample in self.samples]
        if len(names) != len(set(names)):
            duplicates = find_duplicate_entries(names)
            raise ValueError(f"Found duplicate sample names: {', '.join(duplicates)}")
        return self

    @model_validator(mode="after")
    def validate_unique_file_names(self):
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
        instrument_platforms = [sample.instrument_platform for sample in self.samples]
        if len(set(instrument_platforms)) != 1:
            raise ValueError(
                "Samples within a batch must have the same instrument_platform"
            )
        self.instrument_platform = instrument_platforms[0]
        logging.debug(f"{self.instrument_platform=}")
        return self

    def update_sample_metadata(self, metadata=None) -> None:
        """Update sample metadata with output from decontamination process, or defaults if decontamination is skipped"""
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

    def validate_all_sample_fastqs(self):
        for sample in self.samples:
            if not self.skip_reading_fastqs and sample.reads_in == 0:
                sample.validate_reads_from_fastq()
            else:
                logging.warning(
                    f"Skipping additional FastQ file checks as requested (skip_checks = {self.skip_reading_fastqs}"
                )

    def is_ont(self):
        return self.instrument_platform == "ont"

    def is_illumina(self):
        return self.instrument_platform == "illumina"


class RemoteFile(BaseModel):
    filename: str
    run_id: int
    sample_id: str


def create_batch_from_csv(upload_csv: Path, skip_checks: bool = False) -> UploadBatch:
    records = util.parse_csv(upload_csv)
    return UploadBatch(  # Include upload_csv to enable relative fastq path validation
        samples=[UploadSample(**r, **dict(upload_csv=upload_csv)) for r in records],
        skip_reading_fastqs=skip_checks,
    )
