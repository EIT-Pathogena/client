from collections.abc import Callable, Generator
from concurrent.futures import Future
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from pytest_mock import MockerFixture
from pytest_mock.plugin import _mocker

from pathogena.batch_upload_apis import APIClient, APIError
from pathogena.upload_utils import (
    PreparedFiles,
    SampleMetadata,
    SampleUploadStatus,
    SelectedFile,
    UploadFileType,
    UploadSample,
    prepare_file,
    prepare_files,
    upload_chunk,
    upload_chunks,
    upload_files,
)


@pytest.fixture
def mock_api_client(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    return mocker.MagicMock(spec=APIClient)


class TestPrepareFile:
    @pytest.fixture(autouse=True)
    def setup(self, mocker: Callable[..., Generator[MockerFixture, None, None]]):
        file = {
            "name": "file1.txt",
            "size": 1024,  # 1 KB
            "control": "false",
            "content_type": "text/plain",
        }

        # cast into SampleMetadat
        self.file = cast(SampleMetadata, file)

        self.mock_reads_file1_data = mocker.MagicMock()
        self.mock_reads_file1_data.return_value = b"\x1f\x8b\x08\x08\x22\x4e\x01"
        mocker.patch(
            "pathogena.models.UploadSample.read_file1_data", self.mock_reads_file1_data
        )

        # define upload_data
        self.upload_data = UploadSample(
            sample_name="sample1",
            upload_csv=Path("tests/data/illumina.csv"),
            reads_1=Path("reads/tuberculosis_1_1.fastq"),
            control="positive",
            instrument_platform="illumina",
            collection_date=date(2024, 12, 10),
            country="GBR",
            is_illumina=True,
            is_ont=False,
            # read_file1_data=self.mock_reads_file1_data,
        )

        # Ensure `reads_1_resolved_path` is set
        self.upload_data.reads_1_resolved_path = self.upload_data.reads_1
        # set values to call prepare files
        self.batch_pk = 1
        self.upload_session = 1234
        self.file_data = b"\x1f\x8b\x08\x08\x22\x4e\x01"

    def test_prepare_file_success(self, mock_api_client: Any):
        # mock successful api response
        mock_api_client.batches_uploads_start_create.return_value = httpx.Response(
            status_code=httpx.codes.OK, json={"upload_id": "abc123", "sample_id": 456}
        )

        # call
        result = prepare_file(
            upload_data=self.upload_data,
            file=self.file,
            batch_pk=self.batch_pk,
            upload_session=self.upload_session,
            api_client=mock_api_client,
            chunk_size=5000000,
        )

        assert result == {
            "file": self.file,
            "upload_id": "abc123",
            "batch_id": 1,
            "sample_id": 456,
            "total_chunks": 1,  # 1024/5000000 = 0.0002, rounds to 1 chunk
            "upload_session": 1234,
            "file_data": b"\x1f\x8b\x08\x08\x22\x4e\x01",
        }

    def test_prepare_file_unsuccessful(self, mock_api_client: Any):
        # mock api response with 400 code
        mock_api_client.batches_uploads_start_create.return_value = httpx.Response(
            status_code=httpx.codes.BAD_REQUEST, json={"error": "Bad Request"}
        )

        # call
        result = prepare_file(
            upload_data=self.upload_data,
            file=self.file,
            batch_pk=self.batch_pk,
            upload_session=self.upload_session,
            api_client=mock_api_client,
            chunk_size=5000000,
        )

        assert result == {
            "error": "Bad Request",
            "upload_session": 1234,  ## assert upload session added to response
        }

    def test_prepare_file_apierror(self, mock_api_client: Any):
        # mock api response
        mock_api_client.batches_uploads_start_create.side_effect = APIError(
            "API request failed", 500
        )

        # call
        result = prepare_file(
            upload_data=self.upload_data,
            file=self.file,
            batch_pk=self.batch_pk,
            upload_session=self.upload_session,
            api_client=mock_api_client,
            chunk_size=5000000,
        )

        assert result == {
            "error": "API request failed",
            "status code": 500,
            "upload_session": 1234,
        }


class TestPrepareFiles:
    @pytest.fixture(autouse=True)
    def setup(self):
        # Set up multiple files as dictionaries
        self.file1 = UploadSample(
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

        self.file2 = UploadSample(
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
        self.upload_session = 123

    @pytest.fixture
    def mock_api_client(
        self, mocker: Callable[..., Generator[MockerFixture, None, None]]
    ):
        """Fixture for mocking the APIClient."""
        return mocker.MagicMock(spec=APIClient)

    def test_prepare_files_success(
        self,
        mock_api_client: Any,
        mocker: Callable[..., Generator[MockerFixture, None, None]],
    ):
        # mock a successful start upload session  response
        mock_api_client.batches_samples_start_upload_session_create.return_value = {
            "upload_session": self.upload_session,
        }
        # mock prepare_file with successful preparation of new files
        mocker.patch(
            "pathogena.upload_utils.prepare_file",
            side_effect=[
                {
                    "file": {
                        "name": "file1.txt",
                        "size": 10000000,
                        "type": "text/plain",
                    },
                    "upload_id": "abc123",
                    "batch_id": self.batch_pk,
                    "sample_id": 1,
                    "total_chunks": 2,
                    "upload_session": self.upload_session,
                    "file_data": "file1_data",
                },
                {
                    "file": {
                        "name": "file2.txt",
                        "size": 20000000,
                        "type": "text/plain",
                    },
                    "upload_id": "def456",
                    "batch_id": self.batch_pk,
                    "sample_id": 2,
                    "total_chunks": 4,
                    "upload_session": self.upload_session,
                    "file_data": "file2_data",
                },
            ],
        )

        # list of files to pass to prepare_files
        files = [self.file1, self.file2]

        # prepare sample_uploads for prepare_files
        sample_uploads = {
            "sample1": {
                "batch": 123,
                "file_path": Path("reads/tuberculosis_1_1.fastq.gz"),
                "uploaded_file_name": "tuberculosis_1_1.fastq.gz",
                "created_at": datetime(2024, 12, 10, 12, 00, 00),
                "upload_status": "COMPLETE",
                "upload_id": "abc123",
                "total_chunks": 2,
                "hyphenated_legacy_sample_id": "sample-123",
                "metrics": {
                    "chunks_received": 1,
                    "chunks_total": 2,
                    "upload_status": "COMPLETE",
                    "percentage_complete": 50.0,
                    "upload_speed": 10.0,
                    "time_remaining": 10.0,
                    "estimated_completion_time": datetime(2024, 12, 10, 12, 10, 00),
                },
            },
            "sample2": {
                "batch": 123,
                "file_path": Path("reads/tuberculosis_1_2.fastq.gz"),
                "uploaded_file_name": "tuberculosis_1_2.fastq.gz",
                "created_at": datetime(2024, 12, 10, 12, 00, 00),
                "upload_status": "IN_PROGRESS",
                "upload_id": "def456",
                "total_chunks": 4,
                "hyphenated_legacy_sample_id": "sample-456",
                "metrics": {
                    "chunks_received": 1,
                    "chunks_total": 4,
                    "upload_status": "IN_PROGRESS",
                    "percentage_complete": 25.0,
                    "upload_speed": 10.0,
                    "time_remaining": 20.0,
                    "estimated_completion_time": datetime(2024, 12, 10, 12, 20, 00),
                },
            },
        }

        # cast sample uploads to dict[str,SampleUploadStatus]
        sample_uploads = cast(dict[str, SampleUploadStatus], sample_uploads)

        # call prepare_files
        result = prepare_files(
            self.batch_pk,
            files,
            mock_api_client,
            sample_uploads,
        )

        assert len(result["files"]) == 1  # file1.txt is complete and so is skipped
        assert result["files"][0]["upload_id"] == "def456"  # file2 (in progress)
        assert (
            result["uploadSession"] == self.upload_session
        )  #  upload session is resumed

    def test_prepare_files_apierror(self, mock_api_client: Any):
        # mock api error
        mock_api_client.batches_samples_start_upload_session_create.side_effect = (
            APIError("API request failed when starting upload session", 500)
        )

        # list of files to pass to prepare_files
        files = [self.file1, self.file2]

        # call
        with pytest.raises(APIError) as excinfo:
            prepare_files(self.batch_pk, files, mock_api_client)

        # check error message and status code
        assert "API request failed when starting upload session" in str(excinfo.value)
        assert excinfo.value.status_code == 500


class TestUploadChunks:
    @pytest.fixture(autouse=True)
    def setup(self, mocker: Callable[..., Generator[MockerFixture, None, None]]):
        # Set values for the batch, instrument, and upload session
        self.batch_pk = 123
        self.instrument_code = "INST001"
        self.upload_session = 123

        # mock as_completed to simulate completed futures
        self.mock_future = mocker.MagicMock(spec=Future)
        self.mock_future.result.return_value = mocker.MagicMock(
            status_code=200, text="OK", data={"metrics": "some_metrics"}
        )
        mocker.patch(
            "concurrent.futures.as_completed", return_value=[self.mock_future] * 4
        )  # 4 completed chunks to match mock file

        # Mock process_queue to prevent it from blocking the test
        mocker.patch("pathogena.upload_utils.process_queue", return_value=None)

        # mock as_completed to simulate completed futures
        self.mock_end_upload = mocker.MagicMock()
        self.mock_end_upload.return_value = {
            "status": 200,
            "message": "Upload complete",
        }
        mocker.patch("pathogena.upload_utils.end_upload", self.mock_end_upload)

    # fixture for mock_upload_data
    @pytest.fixture(autouse=True)
    def mock_upload_data(
        self, mocker: Callable[..., Generator[MockerFixture, None, None]]
    ):
        """Fixture for mocked upload data."""
        # mocking UploadFileType with required attributes
        samples = [
            UploadSample(
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
            ),
        ]
        return UploadFileType(
            access_token="access_token",
            batch_pk=123,
            env="env",
            samples=samples,
            on_complete=mocker.MagicMock(),
            on_progress=mocker.MagicMock(),
            max_concurrent_chunks=2,
            max_concurrent_files=2,
            upload_session=456,
            abort_controller=None,
        )

    # fixture for mock_file
    @pytest.fixture(autouse=True)
    def mock_file(self):
        mock_file = SelectedFile(
            file={"file1": "name"},
            upload_id=123,
            batch_pk=456,
            sample_id=678,
            total_chunks=4,
            estimated_completion_time=5,
            time_remaining=3,
            uploadSession=123,
            file_data=[b"chunk1", b"chunk2", b"chunk3", b"chunk4"],
        )
        return mock_file

    # fixture for mock_file_status
    @pytest.fixture
    def mock_file_status(self):
        return {}

    def test_upload_chunks_success(
        self,
        mock_upload_data: UploadFileType,
        mock_file: SelectedFile,
        mock_file_status: dict,
        mocker: Callable[..., Generator[MockerFixture, None, None]],
    ):
        # mock return values for chunk_upload_result
        mock_chunk_upload_response = {
            "status_code": 200,
            "data": {"metrics": "some_metrics"},
        }

        # mock upload_chunk to return a successful result
        mock_upload = mocker.MagicMock()
        mock_upload.json.return_value = mock_chunk_upload_response

        mocker.patch("pathogena.upload_utils.upload_chunk", return_value=mock_upload)

        # call
        upload_chunks(mock_upload_data, mock_file, mock_file_status)

        assert (
            mock_upload_data.on_progress.call_count == 4
        )  # called once for each chunk
        assert mock_upload_data.on_complete.called_once_with(
            mock_file["upload_id"], mock_file["batch_pk"]
        )  # on_complete called once
        # 4 chunks uploaded
        assert mock_file_status[mock_file.get("upload_id")]["chunks_uploaded"] == 4
        assert (
            mock_file_status[mock_file.get("upload_id")]["chunks_uploaded"]
            == mock_file["total_chunks"]
        )
        assert self.mock_end_upload.calledonce  # end_upload called once

    def test_upload_chunks_stop_on_400(
        self,
        mock_upload_data: UploadFileType,
        mock_file: SelectedFile,
        mock_file_status: dict,
        mocker: Callable[..., Generator[MockerFixture, None, None]],
    ):
        # mock the first chunk to succeed and the second to fail with a 400
        # need response json too as check it in code
        mock_upload_1 = mocker.Mock()
        mock_upload_1.status_code = 200
        mock_upload_1.text = "OK"
        mock_upload_1.json = lambda: {
            "status_code": 200,
            "data": {"metrics": "some_metrics"},
        }

        mock_upload_2 = mocker.MagicMock()
        mock_upload_2.status_code = 400
        mock_upload_2.text = "Bad Request"
        mock_upload_2.json = lambda: {"status_code": 400}

        # mock upload_chunk to return the above mocks
        mocker.patch(
            "pathogena.upload_utils.upload_chunk",
            side_effect=[mock_upload_1, mock_upload_2],
        )

        # call
        upload_chunks(mock_upload_data, mock_file, mock_file_status)

        assert mock_upload_data.on_progress.call_count == 1  # only chunk 1 was uploaded
        assert (
            not self.mock_end_upload.called
        )  # end_upload should not be called as 2nd upload failed

    def test_upload_chunks_error_handling(
        self,
        mock_upload_data: UploadFileType,
        mock_file: SelectedFile,
        mock_file_status: dict,
        mocker: Callable[..., Generator[MockerFixture, None, None]],
        caplog: pytest.LogCaptureFixture,
    ):
        # mock the first chunk to raise an exception
        mock_upload_1 = mocker.MagicMock()
        mock_upload_1.json.side_effect = Exception("Some error")

        # mock upload_chunk to return the above mock
        mocker.patch("pathogena.upload_utils.upload_chunk", side_effect=[mock_upload_1])

        # call
        upload_chunks(mock_upload_data, mock_file, mock_file_status)

        assert (
            mock_upload_data.on_progress.call_count == 0
        )  # no chunk was successfully uploaded
        assert (
            not self.mock_end_upload.called
        )  # end_upload should not be called since there was an error
        assert (
            "Error uploading chunk 0 of batch 123:" in caplog.text
        )  # error, chunk number and batch pk captured in logging


class TestUploadFiles:
    @pytest.fixture
    def mock_upload_data(self):
        """Fixture for mocked upload data."""
        # mocking UploadFileType with required attributes
        samples = [
            UploadSample(
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
            ),
            UploadSample(
                sample_name="sample2",
                upload_csv=Path("tests/data/ont.csv"),
                reads_1=Path("reads/tuberculosis_1_1.fastq.gz"),
                control="positive",
                instrument_platform="ont",
                collection_date=date(2024, 12, 10),
                country="GBR",
                is_illumina=False,
                is_ont=True,
            ),
        ]

        return UploadFileType(
            access_token="access_token",
            batch_pk=123,
            env="env",
            samples=samples,
            on_complete=None,
            on_progress=None,
            max_concurrent_chunks=2,
            max_concurrent_files=2,
            upload_session=456,
            abort_controller=None,
        )

    @pytest.fixture
    def mock_sample_uploads(self):
        """Fixture for mocked sample uploads."""
        # return {"file1.txt": "pending", "file2.txt": "pending"}
        return None

    @pytest.fixture
    def mock_api_client(
        self, mocker: Callable[..., Generator[MockerFixture, None, None]]
    ):
        """Fixture for mocking the APIClient."""
        return mocker.MagicMock(spec=APIClient)

    @pytest.fixture
    def mock_successful_prepare_files(self) -> PreparedFiles:
        """Fixture for successful PreparedFiles."""
        return {
            "files": [
                SelectedFile(
                    file={"file1": "name"},
                    upload_id=456,
                    batch_pk=123,
                    sample_id=678,
                    total_chunks=5,
                    estimated_completion_time=5,
                    time_remaining=3,
                    uploadSession=123,
                    file_data="file data",
                ),
                SelectedFile(
                    file={"file2": "name"},
                    upload_id=789,
                    batch_pk=456,
                    sample_id=890,
                    total_chunks=5,
                    estimated_completion_time=5,
                    time_remaining=3,
                    uploadSession=123,
                    file_data="file2 data",
                ),
            ],
            "uploadSession": 123,
            "uploadSessionData": {"data": "some_data"},
        }

    @pytest.fixture
    def mock_unsuccessful_prepare_files(self) -> dict[str, str]:
        """Fixture for unsuccessful PreparedFiles."""
        return {"API error occurred": "Test error"}

    def test_upload_files_success(
        self,
        mock_upload_data: UploadFileType,
        mock_sample_uploads: None,
        mock_api_client: Any,
        mock_successful_prepare_files: PreparedFiles,
        mocker: Callable[..., Generator[MockerFixture, None, None]],
    ):
        # mock successful prepare files
        prepared_files = mock_successful_prepare_files

        # mock successful upload_chunks
        mock_upload_chunks = mocker.patch(
            "pathogena.upload_utils.upload_chunks", return_value=None
        )

        # mock successful API client response
        mocker.patch.object(
            APIClient,
            "batches_samples_end_upload_session_create",
            return_value=httpx.Response(
                status_code=httpx.codes.OK,
            ),
        )

        # call
        upload_files(
            mock_upload_data, prepared_files, mock_api_client, mock_sample_uploads
        )

        assert mock_upload_chunks.call_count == 2  # upload chunks called for each file
        APIClient.batches_samples_end_upload_session_create.assert_called_once()
        # end session once

    def test_upload_files_prepare_api_error(
        self,
        mock_upload_data: UploadFileType,
        mock_unsuccessful_prepare_files,
        mock_sample_uploads: None,
        mock_api_client: Any,
        mocker: Callable[..., Generator[MockerFixture, None, None]],
        caplog: pytest.LogCaptureFixture,
    ):
        # call
        upload_files(
            mock_upload_data,
            mock_unsuccessful_prepare_files,
            mock_api_client,
            mock_sample_uploads,
        )

        # assert correct error is logged
        assert "Error preparing files: Test error" in caplog.text

    def test_upload_files_chunk_upload_error(
        self,
        mock_upload_data: UploadFileType,
        mock_successful_prepare_files: PreparedFiles,
        mock_sample_uploads: None,
        mock_api_client: Any,
        mocker: Callable[..., Generator[MockerFixture, None, None]],
        caplog: pytest.LogCaptureFixture,
    ):
        # mock successful prepare files
        prepared_files = mock_successful_prepare_files

        # mock upload_chunks with exception
        mock_upload_chunks = mocker.patch(
            "pathogena.upload_utils.upload_chunks",
            side_effect=Exception("Chunk upload error"),
        )

        # mock successful API client response
        mocker.patch.object(
            APIClient,
            "batches_samples_end_upload_session_create",
            return_value=httpx.Response(
                status_code=httpx.codes.OK,
            ),
        )

        # call
        upload_files(
            mock_upload_data, prepared_files, mock_api_client, mock_sample_uploads
        )

        assert mock_upload_chunks.call_count == 2  # upload chunks called twice
        assert (
            "Error uploading file: Chunk upload error" in caplog.text
        )  # correct error is logged
