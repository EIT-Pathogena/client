from enum import Enum
from datetime import date
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, field_validator


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


class Sample(BaseModel):
    batch_name: Optional[str]
    sample_name: str
    reads_1: Path
    reads_2: Optional[Path]
    control: ControlEnum = ControlEnum.none
    collection_date: date
    country: str
    subdivision: Optional[str]
    district: Optional[str]
    specimen_organism: SpecimenOrganismEnum
    host_organism: HostOrganismEnum
    instrument_platform: InstrumentPlatformEnum

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


class Batch(BaseModel):
    samples: list[Sample]
