import pytest

from pydantic import ValidationError

from pathogena import models

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


def test_fail_invalid_fastq_path(invalid_fastq_paths_csv):
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_fastq_paths_csv)


def test_fail_empty_sample_name(empty_sample_name_csv):
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(empty_sample_name_csv)


def test_fail_invalid_control(invalid_control_csv):
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_control_csv)


def test_fail_invalid_specimen_organism(invalid_specimen_organism_csv):
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_specimen_organism_csv)


def test_fail_mixed_instrument_platform(invalid_mixed_platform_csv):
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_mixed_platform_csv)


def test_fail_invalid_instrument_platform(invalid_instrument_platform_csv):
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_instrument_platform_csv)


def test_validate_illumina_model(illumina_sample_csv, illumina_multiple_sample_csv):
    models.create_batch_from_csv(illumina_sample_csv)
    models.create_batch_from_csv(illumina_multiple_sample_csv)


def test_validate_ont_model(ont_sample_csv):
    models.create_batch_from_csv(ont_sample_csv)


def test_validate_fail_invalid_control(invalid_control_csv):
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_control_csv)


def test_validate_fail_invalid_specimen_organism(invalid_specimen_organism_csv):
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_specimen_organism_csv)


def test_validate_fail_mixed_instrument_platform(invalid_mixed_platform_csv):
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_mixed_platform_csv)


def test_validate_fail_invalid_instrument_platform(invalid_instrument_platform_csv):
    with pytest.raises(ValidationError):
        models.create_batch_from_csv(invalid_instrument_platform_csv)


def test_illumina_fastq_reads_in(illumina_sample):
    illumina_sample.validate_reads_from_fastq()
    assert illumina_sample.reads_in == 2


def test_ont_fastq_reads_in(ont_sample):
    ont_sample.validate_reads_from_fastq()
    assert ont_sample.reads_in == 1


def test_gzipped_illumina_input(illumina_gzipped_sample_csv):
    batch = models.create_batch_from_csv(illumina_gzipped_sample_csv)
    batch.validate_all_sample_fastqs()
    assert batch.samples[0].reads_in == 2


def test_gzipped_ont_input(ont_gzipped_sample_csv):
    batch = models.create_batch_from_csv(ont_gzipped_sample_csv)
    batch.validate_all_sample_fastqs()
    assert batch.samples[0].reads_in == 1


def test_not_fastq_gz_match(illumina_mismatched_fastqs_csv):
    with pytest.raises(ValidationError) as excinfo:
        models.create_batch_from_csv(illumina_mismatched_fastqs_csv)
    assert "reads_1 is not a valid file path" in str(excinfo)


def test_fastq_empty(empty_fastq_csv):
    with pytest.raises(ValidationError) as excinfo:
        models.create_batch_from_csv(empty_fastq_csv)
    assert "reads_1 is empty in sample empty-sample" in str(excinfo)


def test_skip_fastq_checks(illumina_sample_csv, caplog):
    batch = models.create_batch_from_csv(illumina_sample_csv, skip_checks=True)
    batch.validate_all_sample_fastqs()
    assert "Skipping additional FastQ file checks" in caplog.text
