import multiprocessing
import os

CPU_COUNT = multiprocessing.cpu_count()
DEFAULT_HOST = "portal.eit-pathogena.com"
DEFAULT_APP_HOST = "app.eit-pathogena.com"
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
HOSTILE_INDEX_NAME = "human-t2t-hla-argos985-mycob140"

DEFAULT_CHUNK_SIZE = int(
    os.getenv("NEXT_PUBLIC_CHUNK_SIZE", 10 * 1000 * 1000)
)  # 10000000 = 10 mb
DEFAULT_MAX_UPLOAD_RETRIES = int(os.getenv("MAX_UPLOAD_RETRIES", 3))
DEFAULT_RETRY_DELAY = int(os.getenv("RETRY_DELAY", 2))
