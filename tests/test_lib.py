from gpas import lib


def test_fastq_gz_match(human_1_1_fastq_gz, human_1_2_fastq_gz):
    assert lib.valid_fastq(human_1_1_fastq_gz, human_1_2_fastq_gz)


def test_not_fastq_gz_match(bad_1_1_fastq_gz, human_1_2_fastq_gz, caplog):
    assert not lib.valid_fastq(bad_1_1_fastq_gz, human_1_2_fastq_gz)
    assert (
        "FASTQ files tests/data/reads/bad_1_1.fastq.gz and tests/data/reads/human_1_2.fastq.gz do not have the same number of lines"
        in caplog.text
    )


def test_fastq_match(sars_cov_2_1_1_fastq, sars_cov_2_1_2_fastq):
    assert lib.valid_fastq(sars_cov_2_1_1_fastq, sars_cov_2_1_2_fastq)


def test_fastq_empty_ont(empty_fastq_1):
    assert not lib.valid_fastq(empty_fastq_1)


def test_fastq_gz_empty_ont(empty_fastq_gz_1):
    assert not lib.valid_fastq(empty_fastq_gz_1)


def test_fastq_empty_illumina(empty_fastq_1, empty_fastq_2):
    assert not lib.valid_fastq(empty_fastq_1, empty_fastq_2)


def test_fastq_gz_empty_illumina(empty_fastq_gz_1, empty_fastq_gz_2):
    assert not lib.valid_fastq(empty_fastq_gz_1, empty_fastq_gz_2)
