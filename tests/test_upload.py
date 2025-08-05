from collections.abc import Callable, Generator
from concurrent.futures import Future
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from pytest_mock import MockerFixture

from gpas.batch_upload_apis import APIError, UploadAPIClient
from gpas.upload_utils import (
    OnComplete,
    OnProgress,
    PreparedFiles,
    SampleFileMetadata,
    SampleFileUploadStatus,
    SelectedFile,
    UploadData,
    UploadMetrics,
    UploadSample,
    prepare_file,
    prepare_files,
    upload_chunks,
    upload_files,
)


@pytest.fixture
def mock_api_client(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    return mocker.MagicMock(spec=UploadAPIClient)


class TestPrepareFile:
    @pytest.fixture(autouse=True)
    def setup(self, mocker: Callable[..., Generator[MockerFixture, None, None]]):
        self.file = SampleFileMetadata(
            name="file1.txt",
            size=1024,  # 1 KB
            content_type="text/plain",
            specimen_organism="mycobacteria",
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
        )
        self.sample_id = "99999999-9999-9999-9999-999999999999"

        # set values to call prepare files
        self.batch_pk = "11111111-1111-1111-1111-111111111111"
        self.upload_session = 1234
        self.file_data = b"\x1f\x8b\x08\x08\x22\x4e\x01"

    def test_prepare_file_success(self, mock_api_client: Any):
        # mock successful api response
        mock_api_client.batches_uploads_start_file_upload.return_value = httpx.Response(
            status_code=httpx.codes.OK,
            json={
                "upload_id": "abc123",
                "sample_id": "99999999-9999-9999-9999-999999999999",
                "sample_file_id": 456,
            },
        )

        # call
        result = prepare_file(
            resolved_path=self.upload_data.reads_1_resolved_path,
            file_metadata=self.file,
            batch_pk=self.batch_pk,
            upload_session=self.upload_session,
            api_client=mock_api_client,
            sample_id=self.sample_id,
            chunk_size=5000000,
        )

        with open("tests/data/reads/tuberculosis_1_1.fastq", "rb") as file:
            file_data_to_compare = file.read()

        assert result == {
            "file": self.file,
            "upload_id": "abc123",
            "batch_id": "11111111-1111-1111-1111-111111111111",
            "sample_id": "99999999-9999-9999-9999-999999999999",
            "sample_file_id": 456,
            "total_chunks": 1,  # 1024/5000000 = 0.0002, rounds to 1 chunk
            "upload_session": 1234,
            "file_data": file_data_to_compare,
        }

    def test_prepare_file_unsuccessful(self, mock_api_client: Any):
        # mock api response with 400 code
        mock_api_client.batches_uploads_start_file_upload.return_value = httpx.Response(
            status_code=httpx.codes.BAD_REQUEST, json={"error": "Bad Request"}
        )

        # call
        result = prepare_file(
            resolved_path=self.upload_data.reads_1_resolved_path,
            file_metadata=self.file,
            batch_pk=self.batch_pk,
            upload_session=self.upload_session,
            sample_id=self.sample_id,
            api_client=mock_api_client,
            chunk_size=5000000,
        )

        assert result == {
            "error": "Bad Request",
            "upload_session": 1234,  ## assert upload session added to response
        }

    def test_prepare_file_apierror(self, mock_api_client: Any):
        # mock api response
        mock_api_client.batches_uploads_start_file_upload.side_effect = APIError(
            "API request failed", 500
        )

        # call
        result = prepare_file(
            resolved_path=self.upload_data.reads_1_resolved_path,
            file_metadata=self.file,
            batch_pk=self.batch_pk,
            upload_session=self.upload_session,
            sample_id=self.sample_id,
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
        self.sample_summaries = [
            {"sample_id": "11111111-1111-1111-1111-111111111111"},
            {"sample_id": "11111111-1111-1111-1111-111111111111"},
            {"sample_id": "22222222-2222-2222-2222-222222222222"},
            {"sample_id": "22222222-2222-2222-2222-222222222222"},
        ]

    @pytest.fixture
    def mock_api_client(
        self, mocker: Callable[..., Generator[MockerFixture, None, None]]
    ):
        """Fixture for mocking the APIClient."""
        return mocker.MagicMock(spec=UploadAPIClient)

    def test_prepare_files_success(
        self,
        mock_api_client: Any,
        mocker: Callable[..., Generator[MockerFixture, None, None]],
    ):
        # mock a successful start upload session  response
        mock_api_client.batches_samples_start_upload_session_create.return_value = {
            "upload_session": self.upload_session,
            "sample_summaries": self.sample_summaries,
        }
        # mock prepare_file with successful preparation of new files
        mocker.patch(
            "gpas.upload_utils.prepare_file",
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
                {
                    "file": {
                        "name": "file1.txt",
                        "size": 10000000,
                        "type": "text/plain",
                    },
                    "upload_id": "qwe456",
                    "batch_id": self.batch_pk,
                    "sample_id": 3,
                    "total_chunks": 2,
                    "upload_session": self.upload_session,
                    "file_data": "file2_data",
                },
            ],
        )

        # list of files to pass to prepare_files
        files = [self.file1, self.file2]
        result = prepare_files(
            self.batch_pk,
            files,
            mock_api_client,
        )

        assert len(result["files"]) == 3
        assert result["files"][0]["upload_id"] == "abc123"  # file2 (in progress)
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
        mocker.patch("gpas.upload_utils.process_queue", return_value=None)

        # Mock access_token
        dummy_token = "dummy-token"
        mocker.patch("gpas.upload_utils.get_access_token", return_value=dummy_token)

        # mock as_completed to simulate completed futures
        self.mock_end_upload = mocker.patch.object(
            UploadAPIClient,
            "batches_uploads_end_file_upload",
            return_value=httpx.Response(
                status_code=httpx.codes.OK,
            ),
        )

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
        return UploadData(
            access_token="access_token",
            batch_pk=123,
            env="env",
            samples=samples,
            max_concurrent_chunks=2,
            max_concurrent_files=2,
            upload_session=456,
            abort_controller=None,
        )

    # fixture for mock_file
    @pytest.fixture(autouse=True)
    def mock_file(self):
        mock_file = SelectedFile(
            file={"name": "file1"},
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
        mock_upload_data: UploadData,
        mock_file: SelectedFile,
        mock_file_status: dict,
        mocker: Callable[..., Generator[MockerFixture, None, None]],
    ):
        mock_upload_success = httpx.Response(200, json={"metrics": "some_metrics"})

        mocker.patch(
            "gpas.upload_utils.upload_chunk",
            return_value=mock_upload_success,
            # side_effect=mock_upload_success,
        )
        mock_client = mocker.patch(
            "gpas.upload_utils.UploadAPIClient",
        )
        mock_batches_uploads_end_file_upload = mocker.MagicMock()
        mock_batches_uploads_end_file_upload.side_effect = httpx.Response(
            200, json={"metrics": "some_metrics"}
        )
        mock_client.batches_uploads_end_file_upload = (
            mock_batches_uploads_end_file_upload
        )

        upload_chunks(mock_upload_data, mock_file, mock_file_status)

        assert mock_upload_data.on_complete == OnComplete(
            mock_file["upload_id"], mock_upload_data.batch_pk
        )  # all 4 chunks uploaded
        assert mock_file_status[mock_file.get("upload_id")]["chunks_uploaded"] == 4
        assert (
            mock_file_status[mock_file.get("upload_id")]["chunks_uploaded"]
            == mock_file["total_chunks"]
        )
        assert (
            self.mock_end_upload.calledonce
        )  # batches_uploads_end_file_upload called once

    def test_upload_chunks_retry_on_400(
        self,
        mock_upload_data: UploadData,
        mock_file: SelectedFile,
        mock_file_status: dict,
        mocker: Callable[..., Generator[MockerFixture, None, None]],
        caplog: pytest.LogCaptureFixture,
    ):
        # mock the first chunk to succeed and the following to fail with a 400
        # need response json too as check it in code
        mock_upload_success = mocker.Mock()
        mock_upload_success.status_code = 200
        mock_upload_success.text = "OK"
        mock_upload_success.json = lambda: {"metrics": "some_metrics"}

        mock_upload_fail = mocker.MagicMock()
        mock_upload_fail.status_code = 400
        mock_upload_fail.text = "Bad Request"
        mock_upload_fail.json = lambda: {"status_code": 400}

        mock_upload_fail_2 = mocker.MagicMock()
        mock_upload_fail_2.status_code = 400
        mock_upload_fail_2.text = "Bad Request Retry"
        mock_upload_fail_2.json = lambda: {"status_code": 400}

        mock_upload_fail_3 = mocker.MagicMock()
        mock_upload_fail_3.status_code = 400
        mock_upload_fail_3.text = "Bad Request Third"
        mock_upload_fail_3.json = lambda: {"status_code": 400}

        # mock upload_chunk to return the above mocks
        mock_upload_chunk = mocker.patch(
            "gpas.upload_utils.upload_chunk",
            side_effect=[
                mock_upload_success,
                mock_upload_fail,
                mock_upload_fail_2,
                mock_upload_fail_3,
            ],
        )

        # call
        upload_chunks(mock_upload_data, mock_file, mock_file_status)

        assert mock_upload_data.on_progress == OnProgress(
            upload_id=mock_file["upload_id"],
            batch_pk=mock_upload_data.batch_pk,
            progress=25,
            metrics="some_metrics",
        )  # only chunk 1 of 4 was uploaded
        assert mock_upload_data.on_complete is None  # not completed all chunks
        assert (
            not self.mock_end_upload.called
        )  # batches_uploads_end_file_upload should not be called as 2nd upload failed
        assert mock_upload_chunk.call_count == 4
        assert (
            "Retrying upload of chunk 1" in caplog.text
        )  # retrying upload captured in logging
        assert (
            "Attempt 3 of 3" in caplog.text
        )  # retry has been done DEFAULT_MAX_UPLOAD_RETRIES times

    def test_upload_chunks_error_handling(
        self,
        mock_upload_data: UploadData,
        mock_file: SelectedFile,
        mock_file_status: dict,
        mocker: Callable[..., Generator[MockerFixture, None, None]],
        caplog: pytest.LogCaptureFixture,
    ):
        # mock the first chunk to raise an exception
        mock_upload_1 = mocker.MagicMock()
        mock_upload_1.json.side_effect = Exception("Some error")

        mock_upload_2 = mocker.MagicMock()
        mock_upload_2.json.side_effect = Exception("Some error")

        mock_upload_3 = mocker.MagicMock()
        mock_upload_3.json.side_effect = Exception("Some error")

        # mock upload_chunk to return the above mock
        mocker.patch(
            "gpas.upload_utils.upload_chunk",
            side_effect=[mock_upload_1, mock_upload_2, mock_upload_3],
        )

        # call
        upload_chunks(mock_upload_data, mock_file, mock_file_status)

        assert mock_upload_data.on_progress is None  # no progress, errors before
        assert mock_upload_data.on_complete is None  # not completed all chunks
        assert not self.mock_end_upload.called  # batches_uploads_end_file_upload should not be called since there was an error
        assert (
            "Retrying upload of chunk 0" in caplog.text
        )  # retrying upload captured in logging
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

        return UploadData(
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
        return mocker.MagicMock(spec=UploadAPIClient)

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
        mock_upload_data: UploadData,
        mock_sample_uploads: None,
        mock_api_client: Any,
        mock_successful_prepare_files: PreparedFiles,
        mocker: Callable[..., Generator[MockerFixture, None, None]],
    ):
        # mock successful prepare files
        prepared_files = mock_successful_prepare_files

        # mock successful upload_chunks
        mock_upload_chunks = mocker.patch(
            "gpas.upload_utils.upload_chunks", return_value=None
        )

        # mock successful API client response
        mocker.patch.object(
            UploadAPIClient,
            "batches_samples_end_upload_session_create",
            return_value=httpx.Response(
                status_code=httpx.codes.OK,
            ),
        )

        # call
        upload_files(
            mock_upload_data,
            prepared_files,
            mock_api_client,
        )

        assert mock_upload_chunks.call_count == 2  # upload chunks called for each file
        mock_api_client.batches_samples_end_upload_session_create.assert_called_once()
        # end session once

    def test_upload_files_prepare_api_error(
        self,
        mock_upload_data: UploadData,
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
        )

        # assert correct error is logged
        assert "Error preparing files: Test error" in caplog.text

    def test_upload_files_chunk_upload_error(
        self,
        mock_upload_data: UploadData,
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
            "gpas.upload_utils.upload_chunks",
            side_effect=Exception("Chunk upload error"),
        )

        # mock successful API client response
        mocker.patch.object(
            UploadAPIClient,
            "batches_samples_end_upload_session_create",
            return_value=httpx.Response(
                status_code=httpx.codes.OK,
            ),
        )

        # call
        upload_files(mock_upload_data, prepared_files, mock_api_client)

        assert mock_upload_chunks.call_count == 2  # upload chunks called twice
        assert (
            "Error uploading file: Chunk upload error" in caplog.text
        )  # correct error is logged
