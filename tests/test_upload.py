import logging
from concurrent.futures import Future
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from pathogena.client.upload_client import APIError, UploadAPIClient
from pathogena.log_utils import httpx_hooks
from pathogena.models import UploadSample
from pathogena.tasks import upload
from pathogena.tasks.upload import (
    start_upload_session,
    upload_chunks,
    upload_fastq_files,
)
from pathogena.types import (
    OnComplete,
    OnProgress,
    PreparedFile,
    Sample,
    SampleFileMetadata,
    UploadData,
    UploadingFile,
    UploadSession,
)

TEST_UPLOAD_SESSION_ID = 123


class TestUploadBase:
    @pytest.fixture(autouse=True)
    def setup(self):
        # Set values for the batch and instrument
        self.batch_id = "00000000-0000-0000-0000-000000000000"
        self.sample_id = "11111111-1111-1111-1111-111111111111"
        self.instrument_code = "INST001"
        self.upload_session_id = TEST_UPLOAD_SESSION_ID
        self.file_data = b"\x1f\x8b\x08\x08\x22\x4e\x01"


@pytest.fixture(autouse=True)
def mock_token():
    get_token_patch = patch("pathogena.client.env.get_access_token")
    get_token_mock = get_token_patch.start()
    get_token_mock.return_value = "test_token"

    yield get_token_mock

    get_token_patch.stop()


@pytest.fixture
def upload_sample_1() -> UploadSample:
    return UploadSample(
        sample_name="sample1",
        upload_csv=Path("tests/data/illumina.csv"),
        reads_1=Path("reads/tuberculosis_1_1.fastq.gz"),
        reads_2=Path("reads/tuberculosis_1_2.fastq.gz"),
        control="positive",
        instrument_platform="illumina",
        collection_date=date(2024, 12, 10),
        country="GBR",
        is_illumina=True,
        is_ont=False,
    )


@pytest.fixture
def upload_sample_2() -> UploadSample:
    return UploadSample(
        sample_name="sample2",
        upload_csv=Path("tests/data/ont.csv"),
        reads_1=Path("reads/tuberculosis_1_1.fastq.gz"),
        reads_2=None,
        control="positive",
        instrument_platform="ont",
        collection_date=date(2024, 12, 10),
        country="GBR",
        is_illumina=False,
        is_ont=True,
    )


# fixture for mock_upload_data
@pytest.fixture(autouse=True)
def upload_data(upload_sample_1, upload_sample_2):
    """Fixture for mocked upload data."""
    # mocking UploadFileType with required attributes
    samples = [upload_sample_1, upload_sample_2]
    return UploadData(
        access_token="access_token",
        batch_pk=123,
        env="env",
        samples=samples,
        max_concurrent_chunks=2,
        max_concurrent_files=2,
        upload_session_id=456,
        abort_controller=None,
    )


@pytest.fixture
def sample_summarries() -> list[dict]:
    return [
        {"sample_id": "11111111-1111-1111-1111-111111111111"},
        {"sample_id": "11111111-1111-1111-1111-111111111111"},
        {"sample_id": "22222222-2222-2222-2222-222222222222"},
        {"sample_id": "22222222-2222-2222-2222-222222222222"},
    ]


@pytest.fixture()
def prepared_file(upload_sample_1):
    return PreparedFile(upload_sample=upload_sample_1, file_side=1)


@pytest.fixture()
def uploading_file(prepared_file):
    return UploadingFile(
        file_id=1,
        upload_id="1",
        sample_id="test_sample_id",
        batch_id="test_batch_id",
        upload_session_id=0,
        total_chunks=4,
        prepared_file=prepared_file,
    )


@pytest.fixture
def sample_file_metadata() -> SampleFileMetadata:
    return SampleFileMetadata(
        name="file1.txt",
        size=1024,  # 1 KB
        content_type="text/plain",
        specimen_organism="mycobacteria",
        resolved_path=None,
        control="test_control",
    )


@pytest.fixture
def mock_httpx_client():
    return MagicMock(spec=httpx.Client)


@pytest.fixture
def upload_api_client(mock_httpx_client, mock_token):
    return UploadAPIClient("test_url", mock_httpx_client, TEST_UPLOAD_SESSION_ID)


@pytest.fixture
def upload_session(upload_sample_1, upload_sample_2) -> UploadSession:
    """Fixture for creating an upload session."""
    return UploadSession(
        session_id=123,
        name="session",
        samples=[
            Sample(
                instrument_platform="illumina",
                files=[
                    UploadingFile(
                        file_id=1,
                        upload_id="1",
                        sample_id="test_sample_id",
                        batch_id="test_batch_id",
                        upload_session_id=0,
                        total_chunks=2,
                        prepared_file=PreparedFile(upload_sample_1, 1),
                    ),
                    UploadingFile(
                        file_id=2,
                        upload_id="2",
                        sample_id="test_sample_id",
                        batch_id="test_batch_id",
                        upload_session_id=0,
                        total_chunks=2,
                        prepared_file=PreparedFile(upload_sample_1, 2),
                    ),
                ],
            ),
            Sample(
                instrument_platform="ont",
                files=[
                    UploadingFile(
                        file_id=3,
                        upload_id="3",
                        sample_id="test_sample_id",
                        batch_id="test_batch_id",
                        upload_session_id=0,
                        total_chunks=2,
                        prepared_file=PreparedFile(upload_sample_2, 1),
                    )
                ],
            ),
        ],
    )


class TestPrepareFile(TestUploadBase):
    def test_prepare_file_success(
        self,
        upload_api_client: UploadAPIClient,
        upload_sample_1: UploadSample,
        mock_httpx_client: MagicMock,
    ):
        prepared_file = PreparedFile(upload_sample=upload_sample_1, file_side=1)

        # mock successful api response
        mock_httpx_client.post.return_value = httpx.Response(
            status_code=httpx.codes.OK,
            json={
                "upload_id": "test_upload_id",
                "sample_id": "test_sample_id",
                "sample_file_id": 1,
            },
        )

        uploading_file = upload_api_client.start_file_upload(
            file=prepared_file,
            batch_id=self.batch_id,
            sample_id=self.sample_id,
            upload_session_id=self.upload_session_id,
            chunk_size=5000000,
        )

        assert uploading_file == UploadingFile(
            file_id=1,
            upload_id="test_upload_id",
            sample_id="test_sample_id",
            batch_id=self.batch_id,
            upload_session_id=self.upload_session_id,
            total_chunks=1,
            prepared_file=prepared_file,
        )

    def test_prepare_file_unsuccessful(
        self,
        upload_api_client: UploadAPIClient,
        prepared_file: PreparedFile,
        mock_httpx_client: MagicMock,
    ):
        # mock api response with 400 code
        mock_httpx_client.post.return_value = httpx.Response(
            status_code=httpx.codes.BAD_REQUEST, json={"error": "Bad Request"}
        )

        with pytest.raises(APIError):
            upload_api_client.start_file_upload(
                file=prepared_file,
                batch_id=self.batch_id,
                sample_id=self.sample_id,
                upload_session_id=self.upload_session_id,
                chunk_size=5000000,
            )

    def test_prepare_file_api_error(
        self,
        upload_api_client: UploadAPIClient,
        prepared_file: PreparedFile,
        mock_httpx_client: MagicMock,
    ):
        # mock api error with 500 code
        mock_httpx_client.post.side_effect = APIError("API request failed", 500)

        with pytest.raises(APIError):
            upload_api_client.start_file_upload(
                file=prepared_file,
                batch_id=self.batch_id,
                sample_id=self.sample_id,
                upload_session_id=self.upload_session_id,
                chunk_size=5000000,
            )


class TestPrepareFiles:
    @pytest.fixture(autouse=True)
    def setup(self):
        # Set up multiple files as dictionaries
        self.upload_sample1 = UploadSample(
            sample_name="sample1",
            upload_csv=Path("tests/data/illumina.csv"),
            reads_1=Path("reads/tuberculosis_1_1.fastq.gz"),
            reads_2=Path("reads/tuberculosis_1_2.fastq.gz"),
            control="positive",
            instrument_platform="illumina",
            collection_date=date(2024, 12, 10),
            country="GBR",
            is_illumina=True,
            is_ont=False,
        )

        self.upload_sample2 = UploadSample(
            sample_name="sample2",
            upload_csv=Path("tests/data/ont.csv"),
            reads_1=Path("reads/tuberculosis_1_1.fastq.gz"),
            reads_2=None,
            control="positive",
            instrument_platform="ont",
            collection_date=date(2024, 12, 10),
            country="GBR",
            is_illumina=False,
            is_ont=True,
        )

        # Set values for the batch and instrument
        self.batch_pk = 1
        self.instrument_code = "INST001"
        self.upload_session_id = 123
        self.sample_summaries = [
            {"sample_id": "11111111-1111-1111-1111-111111111111"},
        ]

    def test_prepare_files_success(
        self,
    ):
        # list of files to pass to prepare_files
        upload_samples = [self.upload_sample1]

        mock_api_client = MagicMock(spec=UploadAPIClient)

        # mock a successful start upload session  response
        mock_api_client.start_upload_session.return_value = [
            self.upload_session_id,
            "test_name",
            self.sample_summaries,
        ]

        mock_api_client.start_file_upload.side_effect = [
            UploadingFile(
                file_id=1,
                upload_id="test_upload_id_1",
                sample_id="test_sample_id",
                batch_id="test_batch_id",
                upload_session_id=0,
                total_chunks=10,
                prepared_file=PreparedFile(self.upload_sample1, 1),
            ),
            UploadingFile(
                file_id=2,
                upload_id="test_upload_id_2",
                sample_id="test_sample_id",
                batch_id="test_batch_id",
                upload_session_id=0,
                total_chunks=10,
                prepared_file=PreparedFile(self.upload_sample1, 2),
            ),
        ]

        upload_session = start_upload_session(
            self.batch_pk,
            upload_samples,
            mock_api_client,
        )

        assert len(upload_session.samples) == 1
        assert len(upload_session.samples[0].files) == 2
        assert (
            upload_session.samples[0].files[0].upload_id == "test_upload_id_1"
        )  # file2 (in progress)
        assert (
            upload_session.samples[0].files[1].upload_id == "test_upload_id_2"
        )  # file2 (in progress)


class TestUploadChunks:
    @pytest.fixture(autouse=True)
    def setup(self):
        # Set values for the batch, instrument, and upload session
        self.batch_pk = 123
        self.instrument_code = "INST001"
        self.upload_session = 123

        # mock as_completed to simulate completed futures
        self.mock_future = MagicMock(spec=Future)
        self.mock_future.result.return_value = MagicMock(
            status_code=200, text="OK", data={"metrics": "some_metrics"}
        )
        patch(
            "concurrent.futures.as_completed", return_value=[self.mock_future] * 4
        )  # 4 completed chunks to match mock file

        # Mock process_queue to prevent it from blocking the test
        patch("pathogena.upload_utils.process_queue", return_value=None)

        # Mock access_token
        dummy_token = "dummy-token"
        patch("pathogena.upload_utils.get_access_token", return_value=dummy_token)

        # mock as_completed to simulate completed futures
        self.mock_end_upload = patch.object(
            UploadAPIClient,
            "end_file_upload",
            return_value=httpx.Response(
                status_code=httpx.codes.OK,
            ),
        ).start()

    def test_upload_chunks_success(
        self,
        upload_data: UploadData,
        uploading_file: UploadingFile,
    ):
        mock_upload_success = httpx.Response(200, json={"metrics": "some_metrics"})
        patch_upload_chunk = patch(
            "pathogena.client.upload_client.UploadAPIClient.upload_chunk",
            return_value=mock_upload_success,
        )
        patch_upload_chunk.start()

        patch_client = patch(
            "pathogena.client.upload_client.UploadAPIClient",
        )
        mock_client = patch_client.start()

        mock_end_file_upload = MagicMock()
        mock_end_file_upload.side_effect = mock_upload_success
        mock_client.end_file_upload = mock_end_file_upload

        client = UploadAPIClient()
        upload_chunks(client, upload_data, uploading_file)

        assert upload_data.on_complete == OnComplete(
            uploading_file.upload_id, upload_data.batch_pk
        )  # all 4 chunks uploaded
        assert (
            upload_data.on_progress is not None
            and upload_data.on_progress.progress == 100
        )

        assert self.mock_end_upload.calledonce  # end_file_upload called once
        patch_upload_chunk.stop()
        patch_client.stop()

    def test_upload_chunks_retry_on_400(
        self,
        upload_data: UploadData,
        uploading_file: UploadingFile,
        mock_httpx_client: MagicMock,
    ):
        success_response = httpx.Response(
            status_code=httpx.codes.OK,
            json={"metrics": "some_metrics"},
        )
        fail_response = httpx.Response(
            status_code=httpx.codes.BAD_REQUEST,
            json={},
        )

        mock_httpx_client.post.side_effect = [
            fail_response,
            fail_response,
            success_response,
            success_response,
            success_response,
            success_response,
        ]
        client = UploadAPIClient("", mock_httpx_client, 1)

        # call
        upload_chunks(client, upload_data, uploading_file)

        assert upload_data.on_progress == OnProgress(
            upload_id=uploading_file.upload_id,
            batch_pk=upload_data.batch_pk,
            progress=100,
            metrics="some_metrics",
        )


class TestUploadFiles:
    @pytest.fixture(autouse=True)
    def setup(self):
        # Set up multiple files as dictionaries
        self.upload_sample1 = UploadSample(
            sample_name="sample1",
            upload_csv=Path("tests/data/illumina.csv"),
            reads_1=Path("reads/tuberculosis_1_1.fastq.gz"),
            reads_2=Path("reads/tuberculosis_1_2.fastq.gz"),
            control="positive",
            instrument_platform="illumina",
            collection_date=date(2024, 12, 10),
            country="GBR",
            is_illumina=True,
            is_ont=False,
        )

    @pytest.fixture
    def mock_fail_to_start_upload_session(self) -> dict[str, str]:
        """Fixture for unsuccessful PreparedFiles."""
        return {"API error occurred": "Test error"}

    def test_upload_files_success(
        self,
        upload_data: UploadData,
        upload_api_client: UploadAPIClient,
        upload_session: UploadSession,
    ):
        patch_upload_chunks = patch.object(
            UploadAPIClient,
            "upload_chunk",
            return_value=httpx.Response(
                status_code=httpx.codes.OK,
            ),
        )
        mock_upload_chunks = patch_upload_chunks.start()

        patch_end_upload_session = patch.object(
            UploadAPIClient,
            "end_upload_session",
            return_value=httpx.Response(
                status_code=httpx.codes.OK,
            ),
        )
        mock_end_upload_session = patch_end_upload_session.start()

        upload_fastq_files(
            upload_api_client,
            upload_data,
            upload_session,
        )

        assert mock_upload_chunks.call_count == 6  # upload chunks called for each file
        mock_end_upload_session.assert_called_once()

        patch_upload_chunks.stop()
        patch_end_upload_session.stop()

    def test_upload_files_upload_chunks_error(
        self,
        upload_data: UploadData,
        upload_session: UploadSession,
        upload_api_client: Any,
    ):
        patch_upload_chunks = patch.object(
            UploadAPIClient,
            "upload_chunk",
            return_value=httpx.Response(
                status_code=httpx.codes.BAD_REQUEST,
            ),
        )
        patch_upload_chunks.start()

        patch_end_upload_session = patch.object(
            UploadAPIClient,
            "end_upload_session",
            return_value=httpx.Response(
                status_code=httpx.codes.BAD_REQUEST,
            ),
        )
        patch_end_upload_session.start()

        patch_logging = patch("logging.error")
        mock_logging = patch_logging.start()

        upload_fastq_files(upload_api_client, upload_data, upload_session)

        for sample in upload_session.samples:
            for file in sample.files:
                for chunk_index in range(0, 1):
                    e = "Expecting value: line 1 column 1 (char 0)"
                    mock_logging.assert_any_call(
                        f"Error uploading chunk {chunk_index} for file: {file.upload_id} of batch {upload_data.batch_pk}: {str(e)}"
                    )

        mock_logging.assert_any_call("Failed to end upload session for batch 123.")

        patch_upload_chunks.stop()
        patch_end_upload_session.stop()


class TestLogDownloadMappingCSV:
    @staticmethod
    def make_dummy_batch():
        """
        Create a minimal UploadBatch-like object with one sample,
        so upload_batch doesn't blow up before our helper call.
        """
        sample = MagicMock(sample_name="test", amplicon_scheme="test_amplicon")
        batch = MagicMock(
            samples=[sample],
        )
        return batch

    class DummyFile:
        def __init__(self, name, path, sample_id):
            self.prepared_file = MagicMock(name=name, path=path)
            self.sample_id = sample_id

    class DummySession:
        def __init__(self, name, session_id, samples):
            self.name = name
            self.session_id = session_id
            self.samples = samples

    @patch("pathogena.tasks.upload.httpx.Client")
    def test_log_download_mapping_file_success(self, mock_client: MagicMock):
        """Test download csv logging called as expected"""

        batch_id = "batch123"
        file_name = "mapping"
        token = "tok-xyz"
        fake_client = MagicMock()

        # mock the context‐manager
        mock_client.return_value.__enter__.return_value = fake_client
        mock_client.return_value.__exit__.return_value = None

        # call
        upload.log_download_mapping_file_to_portal(
            batch_id=batch_id, file_name=file_name, token=token
        )

        # check called once
        assert mock_client.call_count == 1

        # check kwargs as expected
        _, kwargs = mock_client.call_args
        assert kwargs["event_hooks"] is httpx_hooks
        assert isinstance(kwargs["transport"], httpx.HTTPTransport)
        assert kwargs["timeout"] == 60

    @patch("pathogena.tasks.upload.upload_fastq_files")
    @patch("pathogena.tasks.upload.log_download_mapping_file_to_portal")
    @patch("pathogena.tasks.upload.util.write_csv")
    @patch("pathogena.tasks.upload.env.get_access_token", return_value="tok-123")
    @patch("pathogena.tasks.upload.start_upload_session")
    @patch("pathogena.tasks.upload.create_batch_on_server")
    def test_upload_batch_calls_portal_logging_on_success(
        self,
        mock_create,
        mock_upload_session,
        mock_token,
        mock_write_csv,
        mock_logger,
        mock_upload_fastq,
        caplog,
    ):
        # mock create_batch_on_server to return dummy IDs
        batch_id = uuid4()
        batch_name = "remote"
        legacy_id = uuid4()
        mock_create.return_value = (batch_id, batch_name, legacy_id)

        # mock the upload session
        fake_file = TestLogDownloadMappingCSV.DummyFile("f1", "/tmp/f1", "sid1")
        sample_obj = MagicMock(files=[fake_file])
        fake_session = TestLogDownloadMappingCSV.DummySession(
            name=batch_name, session_id=123, samples=[sample_obj]
        )
        mock_upload_session.return_value = fake_session

        batch = TestLogDownloadMappingCSV.make_dummy_batch()

        # call upload batch
        upload.upload_batch(batch=batch, save=True, validate_only=False)

        # assert expected calls made once
        mock_write_csv.assert_called_once_with(
            [
                {
                    "batch_name": batch_name,
                    "sample_name": fake_file.prepared_file.name,
                    "remote_sample_name": fake_file.sample_id,
                    "remote_batch_name": batch_name,
                    "remote_batch_id": batch_id,
                }
            ],
            f"{batch_name}.mapping.csv",
        )
        mock_logger.assert_called_once_with(
            str(batch_id),
            batch_name,
            "tok-123",
        )
        mock_upload_fastq.assert_called_once()

        # no log levels of warning or higher
        assert not [rec for rec in caplog.records if rec.levelno >= logging.WARNING]

    @patch("pathogena.tasks.upload.upload_fastq_files")
    @patch(
        "pathogena.tasks.upload.log_download_mapping_file_to_portal",
        side_effect=Exception("noooooo!"),
    )
    @patch("pathogena.tasks.upload.util.write_csv")
    @patch("pathogena.tasks.upload.env.get_access_token", return_value="tok-123")
    @patch("pathogena.tasks.upload.start_upload_session")
    @patch("pathogena.tasks.upload.create_batch_on_server")
    def test_upload_batch_portal_logging_failure(
        self,
        mock_create,
        mock_upload_session,
        mock_token,
        mock_write_csv,
        mock_logger,
        mock_upload_fastq,
        caplog,
    ):
        # mock create_batch_on_server to return dummy IDs
        batch_id = uuid4()
        batch_name = "remote"
        legacy_id = uuid4()
        mock_create.return_value = (batch_id, batch_name, legacy_id)

        # mock the upload session
        fake_file = TestLogDownloadMappingCSV.DummyFile("f1", "/tmp/f1", "sid1")
        sample_obj = MagicMock(files=[fake_file])
        fake_session = TestLogDownloadMappingCSV.DummySession(
            name=batch_name, session_id=123, samples=[sample_obj]
        )
        mock_upload_session.return_value = fake_session

        batch = TestLogDownloadMappingCSV.make_dummy_batch()

        # call upload batch
        upload.upload_batch(batch=batch, save=True, validate_only=False)

        # assert expected calls made once
        mock_write_csv.assert_called_once_with(
            [
                {
                    "batch_name": batch_name,
                    "sample_name": fake_file.prepared_file.name,
                    "remote_sample_name": fake_file.sample_id,
                    "remote_batch_name": batch_name,
                    "remote_batch_id": batch_id,
                }
            ],
            f"{batch_name}.mapping.csv",
        )

        # assert called the logger
        mock_logger.assert_called_once_with(
            str(batch_id),
            batch_name,
            "tok-123",
        )

        # assert logged that failed to log in portal
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert any(
            "Could not log mapping-file download to portal" in r.message
            for r in warnings
        )
