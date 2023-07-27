from enum import Enum
from datetime import date
from pathlib import Path
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


class ControlEnum(Enum):
    positive = "positive"
    negative = "negative"
    none = ""


class SpecimenOrganismEnum(Enum):
    mycobacteria = "mycobacteria"


class HostOrganismEnum(Enum):
    human = "homo sapiens"


class InstrumentPlatformEnum(Enum):
    illumina = "illumina"
    ont = "ont"


class UploadSample(BaseModel):
    batch_name: str = Field(
        default=None, description="Batch name (anonymised prior to upload)"
    )
    sample_name: str = Field(description="Sample name (anonymised prior to upload)")
    reads_1: Path = Field(description="Path of first FASTQ file")
    reads_2: Path = Field(description="Path of second FASTQ file")
    control: ControlEnum = Field(
        default=ControlEnum.none, description="Control status of sample"
    )
    collection_date: date = Field(description="Collection date in yyyy-mm-dd format")
    country: str = Field(description="ISO 3166-2 alpha-3 country code")
    subdivision: str = Field(
        default=None, description="ISO 3166-2 principal subdivision"
    )
    district: str = Field(default=None, description="Granular location")
    specimen_organism: SpecimenOrganismEnum = Field(
        description="Target specimen organism scientific name"
    )
    host_organism: HostOrganismEnum = Field(description="Host organism scientific name")
    instrument_platform: InstrumentPlatformEnum = Field(
        description="DNA sequencing instrument platform"
    )

    @field_validator("reads_1", "reads_2")
    def validate_file_extension(cls, v: Path):
        allowed_extensions = {".fastq", ".fq", ".fastq.gz", ".fq.gz"}
        if v is not None and not v.name.endswith(tuple(allowed_extensions)):
            raise ValueError(
                f"Invalid file extension {v.suffix} for file {v.name}. Allowed extensions are {allowed_extensions}"
            )
        return v

    # @field_validator("reads_1", "reads_2")
    # def validate_file_exists(cls, v: Path):
    #     if v is not None and (not v.exists() or not v.is_file()):
    #         raise ValueError(f"{v} is not a valid file")


class UploadBatch(BaseModel):
    samples: list[UploadSample]
