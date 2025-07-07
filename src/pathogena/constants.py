import multiprocessing
import os
from typing import Literal

PLATFORMS = Literal["illumina", "ont"]

CPU_COUNT = multiprocessing.cpu_count()

DEFAULT_HOST = "portal.eit-pathogena.com"
DEFAULT_APP_HOST = "app.eit-pathogena.com"
DEFAULT_UPLOAD_HOST = "api.upload.eit-pathogena.com"
DEFAULT_PROTOCOL = "https"
DEFAULT_COUNTRY: None = None
DEFAULT_DISTRICT = ""
DEFAULT_SUBDIVISION = ""
DEFAULT_INSTRUMENTPLATFORM = "illumina"
DEFAULT_PIPELINE = "mycobacteria"
DEFAULT_ONT_READ_SUFFIX = ".fastq.gz"
DEFAULT_ILLUMINA_READ1_SUFFIX = "_1.fastq.gz"
DEFAULT_ILLUMINA_READ2_SUFFIX = "_2.fastq.gz"
DEFAULT_MAX_BATCH_SIZE = 50

HOSTILE_INDEX_NAME = "human-t2t-hla-argos985-mycob140"

DEFAULT_CHUNK_SIZE = int(
    os.getenv("NEXT_PUBLIC_CHUNK_SIZE", 10 * 1000 * 1000)
)  # 10000000 = 10 mb
