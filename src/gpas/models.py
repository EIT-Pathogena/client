from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


ALLOWED_EXTENSIONS = (".fastq", ".fq", ".fastq.gz", ".fq.gz")


def validate_file_extension(
    filename: str, allowed_extensions: list = ALLOWED_EXTENSIONS
):
    filename = str(filename)
    return True if filename.endswith(allowed_extensions) else False


class UploadSample(BaseModel):
    batch_name: str = Field(
        default=None, description="Batch name (anonymised prior to upload)"
    )
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
    collection_date: date = Field(description="Collection date in yyyy-mm-dd format")
    country: str = Field(
        min_length=3, max_length=3, description="ISO 3166-2 alpha-3 country code"
    )
    subdivision: str = Field(
        default=None, description="ISO 3166-2 principal subdivision"
    )
    district: str = Field(default=None, description="Granular location")
    specimen_organism: Literal["mycobacteria", ""] = Field(
        description="Target specimen organism scientific name"
    )
    host_organism: str = Field(
        default=None, description="Host organism scientific name"
    )
    # instrument_platform: Literal["illumina", "ont"] = Field(
    instrument_platform: Literal["illumina"] = Field(
        description="DNA sequencing instrument platform"
    )

    @model_validator(mode="after")
    def check_fastqs_are_different(self):
        if self.reads_1 == self.reads_2:
            raise ValueError("reads_1 and reads_2 paths must be different")
        return self

    @model_validator(mode="after")
    def validate_fastqs_by_platform(self):
        reads_1 = self.reads_1
        reads_2 = self.reads_2
        reads_1_resolved_path = self.upload_csv.resolve().parent / reads_1
        reads_2_resolved_path = self.upload_csv.resolve().parent / reads_2
        if self.instrument_platform == "ont":
            if not reads_1_resolved_path.is_file():
                raise ValueError("reads_1 must be a valid FASTQ file path")
            if reads_2_resolved_path.is_file():
                raise ValueError(
                    "reads_2 must be empty where instrument_platform is ont"
                )
            if reads_1 and not validate_file_extension(reads_1.name):
                raise ValueError(
                    f"Invalid file extension for file {self.reads_1.name}. Allowed extensions are {ALLOWED_EXTENSIONS}"
                )
        elif self.instrument_platform == "illumina":
            if (
                not reads_1_resolved_path.is_file()
                or not reads_2_resolved_path.is_file()
            ):
                raise ValueError(
                    "reads_1 and reads_2 must be valid FASTQ file paths where instrument_platform is illumina"
                )
            if reads_1 and not validate_file_extension(reads_1.name):
                raise ValueError(
                    f"Invalid file extension for file {self.reads_1.name}. Allowed extensions are {ALLOWED_EXTENSIONS}"
                )
            if reads_2 and not validate_file_extension(reads_2.name):
                raise ValueError(
                    f"Invalid file extension for file {self.reads_2.name}. Allowed extensions are {ALLOWED_EXTENSIONS}"
                )
        return self

    # @model_validator(pre=True)
    # def lowercase_all_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
    #     return {k: (v.lower() if isinstance(v, str) else v) for k, v in values.items()}


class UploadBatch(BaseModel):
    samples: list[UploadSample]

    @model_validator(mode="after")
    def validate_unique_sample_names(self):
        names = [sample.sample_name for sample in self.samples]
        if len(names) != len(set(names)):
            raise ValueError("Found duplicate sample names")
        return self

    @model_validator(mode="after")
    def validate_unique_file_names(self):
        reads_1_filenames = [str(sample.reads_1.name) for sample in self.samples]
        reads_2_filenames = [str(sample.reads_2.name) for sample in self.samples]
        instrument_platforms = self.samples[0].instrument_platform
        if instrument_platforms == "ont":
            if len(reads_1_filenames) != len(set(reads_1_filenames)):
                raise ValueError("Found duplicate FASTQ filenames")
        elif instrument_platforms == "illumina":
            if len(reads_1_filenames) + len(reads_1_filenames) != len(
                set(reads_1_filenames) | set(reads_2_filenames)
            ):
                raise ValueError("Found duplicate FASTQ filenames")
        return self

    @model_validator(mode="after")
    def validate_single_instrument_platform(self):
        instrument_platforms = [sample.instrument_platform for sample in self.samples]
        if len(set(instrument_platforms)) != 1:
            raise ValueError(
                "Samples within a batch must have the same instrument_platform"
            )
        return self


class RemoteFile(BaseModel):
    filename: str
    run_id: int
    sample_id: str
