"""Init file containing all tasks that can be run from the CLI interface."""

from pathogena.tasks.authentication import authenticate, check_authentication
from pathogena.tasks.download import (
    download,
    download_index,
    download_single,
    fetch_latest_input_files,
)
from pathogena.tasks.prep_samples import (
    build_upload_csv,
    decontaminate_samples_with_hostile,
    validate_upload_permissions,
)
from pathogena.tasks.query import (
    check_for_newer_version,
    check_version_compatibility,
    fetch_output_files,
    fetch_sample,
    get_amplicon_schemes,
    get_credit_balance,
    parse_csv,
    query,
    status,
)
from pathogena.tasks.upload import (
    create_batch_on_server,
    prepare_sample,
    prepare_upload_files,
    remove_file,
    start_upload_session,
    upload_batch,
    upload_chunks,
    upload_fastq_files,
)

__all__ = [
    "query",
    "status",
    "parse_csv",
    "check_version_compatibility",
    "check_for_newer_version",
    "fetch_output_files",
    "get_amplicon_schemes",
    "get_credit_balance",
    "authenticate",
    "check_authentication",
    "download",
    "download_single",
    "download_index",
    "fetch_latest_input_files",
    "fetch_latest_input_files",
    "fetch_sample",
    "prepare_upload_files",
    "upload_batch",
    "create_batch_on_server",
    "upload_fastq_files",
    "upload_chunks",
    "start_upload_session",
    "prepare_sample",
    "remove_file",
    "decontaminate_samples_with_hostile",
    "validate_upload_permissions",
]
