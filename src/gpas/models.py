from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class UploadSample(BaseModel):
    batch_name: str = Field(
        default=None, description="Batch name (anonymised prior to upload)"
    )
    sample_name: str = Field(
        min_length=1, description="Sample name (anonymised prior to upload)"
    )
    upload_csv: Path = Field(description="Absolute path of upload CSV file")
    reads_1: Path = Field(description="Relative path of first FASTQ file")
    reads_2: Path = Field(description="Relative path of second FASTQ file")
    control: str = Field(
        Literal["positive", "negative", ""], description="Control status of sample"
    )
    collection_date: date = Field(description="Collection date in yyyy-mm-dd format")
    country: str = Field(
        min_length=3, max_length=3, description="ISO 3166-2 alpha-3 country code"
    )
    subdivision: str = Field(
        default=None, description="ISO 3166-2 principal subdivision"
    )
    district: str = Field(default=None, description="Granular location")
    specimen_organism: str = Field(
        Literal["mycobacteria"], description="Target specimen organism scientific name"
    )
    host_organism: str = Field(
        default=None, description="Host organism scientific name"
    )
    instrument_platform: str = Field(
        Literal["illumina", "ont"], description="DNA sequencing instrument platform"
    )

    @field_validator("reads_1", "reads_2")
    def validate_file_extension(cls, d: Path):
        allowed_extensions = {".fastq", ".fq", ".fastq.gz", ".fq.gz"}
        if d is not None and not d.name.endswith(tuple(allowed_extensions)):
            raise ValueError(
                f"Invalid file extension {d.suffix} for file {d.name}. Allowed extensions are {allowed_extensions}"
            )
        return d

    # @field_validator("reads_1", "reads_2")
    # def validate_file_exists(cls, v: Path):
    #     if v is not None and (not v.exists() or not v.is_file()):
    #         raise ValueError(f"{v} is not a valid file")

    @model_validator(mode="after")
    def check_fastqs_are_different(self):
        if self.reads_1 == self.reads_2:
            raise ValueError("reads_1 and reads_2 paths must be different")
        return self

    @model_validator(mode="after")
    def validate_fastqs_exist(self):
        if not (self.upload_csv.resolve().parent / self.reads_1).is_file():
            raise ValueError("reads_1 is not a valid file path")
        if not (self.upload_csv.resolve().parent / self.reads_2).is_file():
            raise ValueError("reads_2 is not a valid file path")
        return self

    # @model_validator(pre=True)
    # def lowercase_all_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
    #     return {k: (v.lower() if isinstance(v, str) else v) for k, v in values.items()}
    # @field_validator("reads_1", "reads_2")
    # def validate_file_exists(cls, v: Path):
    #     if v is not None and (not v.exists() or not v.is_file()):
    #         raise ValueError(f"{v} is not a valid file")


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
        for filenames in [reads_1_filenames, reads_2_filenames]:
            if len(filenames) != len(set(filenames)):
                raise ValueError("Found duplicate FASTQ filenames")
        return self


class RemoteFile(BaseModel):
    filename: str
    run_id: int
    sample_id: str
