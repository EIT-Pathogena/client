import multiprocessing
import os

CPU_COUNT = multiprocessing.cpu_count()
DEFAULT_HOST = "portal.eit-pathogena.com"
DEFAULT_UPLOAD_HOST = "api.upload.eit-pathogena.com"
DEFAULT_PROTOCOL = "https"
DEFAULT_METADATA = {
    "country": None,
    "district": "",
    "subdivision": "",
    "instrument_platform": "illumina",
    "pipeline": "mycobacteria",
    "ont_read_suffix": ".fastq.gz",
    "illumina_read1_suffix": "_1.fastq.gz",
    "illumina_read2_suffix": "_2.fastq.gz",
    "max_batch_size": 50,
}
DEFAULT_METADATA = {
    "country": None,
    "district": "",
    "subdivision": "",
    "instrument_platform": "illumina",
    "pipeline": "mycobacteria",
    "ont_read_suffix": ".fastq.gz",
    "illumina_read1_suffix": "_1.fastq.gz",
    "illumina_read2_suffix": "_2.fastq.gz",
    "max_batch_size": 50,
}
HOSTILE_INDEX_NAME = "human-t2t-hla-argos985-mycob140"

DEFAULT_CHUNK_SIZE = int(os.getenv("NEXT_PUBLIC_CHUNK_SIZE", 5000000))  # 5000000 = 5 mb
