from pathlib import Path

import pytest
from pydantic import ValidationError

from gpas import models
from gpas.models import UploadSample

# Doesn't work because it actually uploads data, need to work out a mock system or break down the function
# even further, for now, an authenticated used can un-comment and run the tests.
#
# def test_illumina_2(test_host, illumina_multiple_sample_batch):
#     lib.upload_batch(batch=illumina_multiple_sample_batch, host=test_host)
#     [os.remove(f) for f in os.listdir(".") if f.endswith("fastq.gz")]
#     [os.remove(f) for f in os.listdir(".") if f.endswith(".mapping.csv")]
#
#
# def test_ont_2(test_host, ont_multiple_sample_batch):
#     lib.upload_batch(batch=ont_multiple_sample_batch, host=test_host)
#     [os.remove(f) for f in os.listdir(".") if f.endswith("fastq.gz")]
#     [os.remove(f) for f in os.listdir(".") if f.endswith(".mapping.csv")]


def test_fail_invalid_fastq_path(invalid_fastq_paths_csv: Path) -> None:
    """Test failure for invalid FASTQ file paths.

    Args:
        invalid_fastq_paths_csv (Path): Path to the CSV file with invalid FASTQ paths.
    """
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_fastq_paths_csv)


def test_fail_empty_sample_name(empty_sample_name_csv: Path) -> None:
    """Test failure for empty sample names.

    Args:
        empty_sample_name_csv (Path): Path to the CSV file with empty sample names.
    """
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(empty_sample_name_csv)


def test_fail_invalid_control(invalid_control_csv: Path) -> None:
    """Test failure for invalid control values.

    Args:
        invalid_control_csv (Path): Path to the CSV file with invalid control values.
    """
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_control_csv)


def test_fail_invalid_specimen_organism(invalid_specimen_organism_csv: Path) -> None:
    """Test failure for invalid specimen organism values.

    Args:
        invalid_specimen_organism_csv (Path): Path to the CSV file with invalid specimen organism values.
    """
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_specimen_organism_csv)


def test_fail_mixed_instrument_platform(invalid_mixed_platform_csv: Path) -> None:
    """Test failure for mixed instrument platforms.

    Args:
        invalid_mixed_platform_csv (Path): Path to the CSV file with mixed instrument platforms.
    """
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_mixed_platform_csv)


def test_fail_invalid_instrument_platform(
    invalid_instrument_platform_csv: Path,
) -> None:
    """Test failure for invalid instrument platform values.

    Args:
        invalid_instrument_platform_csv (Path): Path to the CSV file with invalid instrument platform values.
    """
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_instrument_platform_csv)


def test_validate_illumina_model(
    illumina_sample_csv: Path, illumina_multiple_sample_csv: Path
) -> None:
    """Test validation of Illumina model.

    Tests that creating a batch from a valid Illumina csv doesn't raise an exception.

    Args:
        illumina_sample_csv (Path): Path to the CSV file with Illumina sample data.
        illumina_multiple_sample_csv (Path): Path to the CSV file with multiple Illumina sample data.
    """
    models.create_batch_from_csv(illumina_sample_csv)
    models.create_batch_from_csv(illumina_multiple_sample_csv)


def test_validate_ont_model(ont_sample_csv: Path) -> None:
    """Test validation of ONT model.

    Tests that creating a batch from a valid ONT csv doesn't raise an exception.

    Args:
        ont_sample_csv (Path): Path to the CSV file with ONT sample data.
    """
    models.create_batch_from_csv(ont_sample_csv)


def test_validate_sars_cov_2_specimen_organism(
    illumina_sars_cov_2_gzipped_sample_csv: Path,
) -> None:
    """Test validation of SARS-CoV-2 specimen organism.

    Args:
        sars-cov-2_sample_csv (Path): Path to the CSV file with SARS-CoV-2 sample data.
    """
    models.create_batch_from_csv(illumina_sars_cov_2_gzipped_sample_csv)


def test_validate_sars_cov_2_specimen_organism_amp_scheme(
    illumina_sars_cov_2_amp_gzipped_sample_csv: Path,
) -> None:
    """Test validation of SARS-CoV-2 specimen organism.

    Args:
        sars_cov_2_sample_csv (Path): Path to the CSV file with SARS-CoV-2 sample data.
    """
    models.create_batch_from_csv(illumina_sars_cov_2_amp_gzipped_sample_csv)


def test_validate_sars_cov_2_specimen_organism_mix_amp_scheme(
    illumina_sars_cov_2_mix_amp_gzipped_sample_csv: Path,
) -> None:
    """Test validation of SARS-CoV-2 specimen organism.

    Args:
        sars_cov_2_sample_csv (Path): Path to a CSV file with SARS-CoV-2 sample data
        and more than one value for amp scheme in the batch.
    """

    with pytest.raises(ValidationError):
        models.create_batch_from_csv(illumina_sars_cov_2_mix_amp_gzipped_sample_csv)


def test_validate_myco_amp_scheme(
    myco_illumina_amp: Path,
) -> None:
    """Test validation of myco specimen organism.

    Args:
        myco_illumina_amp (Path): Path to a CSV file with myco sample data
        with amp scheme specified.
    """

    with pytest.raises(ValidationError):
        models.create_batch_from_csv(myco_illumina_amp)


def test_validate_fail_invalid_control(invalid_control_csv: Path) -> None:
    """Test validation failure for invalid control values.

    Args:
        invalid_control_csv (Path): Path to the CSV file with invalid control values.
    """
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_control_csv)


def test_validate_fail_invalid_specimen_organism(
    invalid_specimen_organism_csv: Path,
) -> None:
    """Test validation failure for invalid specimen organism values.

    Args:
        invalid_specimen_organism_csv (Path): Path to the CSV file with invalid specimen organism values.
    """
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_specimen_organism_csv)


def test_validate_fail_empty_specimen_organism(
    empty_specimen_organism_csv: Path,
) -> None:
    """Test validation failure for empty specimen organism values.

    Args:
        empty_specimen_organism_csv (Path): Path to the CSV file with empty specimen organism values.
    """
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(empty_specimen_organism_csv)


def test_validate_fail_mixed_instrument_platform(
    invalid_mixed_platform_csv: Path,
) -> None:
    """Test validation failure for mixed instrument platform csvs.

    Args:
        invalid_mixed_platform_csv (Path): Path to the CSV file with mixed instrument platforms.
    """
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_mixed_platform_csv)


def test_validate_fail_invalid_instrument_platform(
    invalid_instrument_platform_csv: Path,
) -> None:
    """Test validation failure for invalid instrument platform values.

    Args:
        invalid_instrument_platform_csv (Path): Path to the CSV file with invalid instrument platform values.
    """
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_instrument_platform_csv)


def test_illumina_fastq_reads_in(illumina_sample: UploadSample) -> None:
    """Test validation of Illumina FASTQ reads.

    Args:
        illumina_sample (UploadSample): Illumina sample to validate.
    """
    illumina_sample.validate_reads_from_fastq()
    assert illumina_sample.reads_in == 2


def test_ont_fastq_reads_in(ont_sample: UploadSample) -> None:
    """Test validation of ONT FASTQ reads.

    Args:
        ont_sample (UploadSample): ONT sample to validate.
    """
    ont_sample.validate_reads_from_fastq()
    assert ont_sample.reads_in == 1


def test_gzipped_illumina_input(illumina_gzipped_sample_csv: Path) -> None:
    """Test validation of gzipped Illumina input.

    Args:
        illumina_gzipped_sample_csv (Path): Path to the CSV file with gzipped Illumina sample data.
    """
    batch = models.create_batch_from_csv(illumina_gzipped_sample_csv)
    batch.validate_all_sample_fastqs()
    assert batch.samples[0].reads_in == 2


def test_gzipped_ont_input(ont_gzipped_sample_csv: Path) -> None:
    """Test validation of gzipped ONT input.

    Args:
        ont_gzipped_sample_csv (Path): Path to the CSV file with gzipped ONT sample data.
    """
    batch = models.create_batch_from_csv(ont_gzipped_sample_csv)
    batch.validate_all_sample_fastqs()
    assert batch.samples[0].reads_in == 1


def test_not_fastq_gz_match(illumina_mismatched_fastqs_csv: Path) -> None:
    """Test failure for mismatched FASTQ files.

    Args:
        illumina_mismatched_fastqs_csv (Path): Path to the CSV file with mismatched Illumina FASTQ files.
    """
    with pytest.raises(ValidationError) as excinfo:
        models.create_batch_from_csv(illumina_mismatched_fastqs_csv)
    assert "reads_1 is not a valid file path" in str(excinfo)


def test_fastq_empty(empty_fastq_csv: Path) -> None:
    """Test failure for empty FASTQ files.

    Args:
        empty_fastq_csv (Path): Path to the CSV file with empty FASTQ files.
    """
    with pytest.raises(ValidationError) as excinfo:
        models.create_batch_from_csv(empty_fastq_csv)
    assert "reads_1 is empty in sample empty-sample" in str(excinfo)


def test_skip_fastq_checks(
    illumina_sample_csv: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test skipping of FASTQ file checks.

    Args:
        illumina_sample_csv (Path): Path to the CSV file with Illumina sample data.
        caplog (pytest.LogCaptureFixture): Fixture to capture log output.
    """
    batch = models.create_batch_from_csv(illumina_sample_csv, skip_checks=True)
    batch.validate_all_sample_fastqs()
    assert "Skipping additional FastQ file checks" in caplog.text
