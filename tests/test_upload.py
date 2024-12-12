from concurrent.futures import Future
from datetime import date
from pathlib import Path

import pytest
from httpx import Response

from pathogena.models import (
    SelectedFile,
    UploadFileType,
    UploadSample,
    prepare_files,
    upload_chunks,
    upload_files,
)
from pathogena.util import (
    APIClient,
    APIError,
    # SelectedFile,
    # UploadFileType,
    prepare_file,
    # prepare_files,
    upload_chunk,
    # upload_chunks,
    # upload_files,
)


@pytest.fixture
def mock_api_client(mocker):
    return mocker.MagicMock(spec=APIClient)


class TestPrepareFile:
    @pytest.fixture(autouse=True)
    def setup(self, mocker):
        self.file = mocker.MagicMock()
        self.file.name = "file1.txt"
        self.file.size = 1024  # 1mb
        self.file.type = "text/plain"

    # set values to call prepare files
    batch_pk = 1
    upload_session = 123

    def test_prepare_file_success(self, mock_api_client):
        # mock successful api response
        mock_api_client.batches_uploads_start_create.return_value = {
            "status": 200,
            "data": {"upload_id": "abc123", "sample_id": 456},
        }

        # call
        result = prepare_file(
            self.file, self.batch_pk, self.upload_session, mock_api_client
        )

        assert result == {
            "file": self.file,
            "upload_id": "abc123",
            "batch_id": 1,
            "sample_id": 456,
            "total_chunks": 1,  # 1024/5000000 = 0.0002, rounds to 1 chunk
            "upload_session": 123,
        }

    def test_prepare_file_unsuccessful(self, mock_api_client):
        # mock api response with 400 code
        mock_api_client.batches_uploads_start_create.return_value = {
            "status": 400,
            "error": "Bad Request",
        }

        # call
        result = prepare_file(
            self.file, self.batch_pk, self.upload_session, mock_api_client
        )

        assert result == {
            "status": 400,
            "error": "Bad Request",
            "upload_session": 123,  ## assert upload session added to response
        }

    def test_prepare_file_apierror(self, mock_api_client):
        # mock api response
        mock_api_client.batches_uploads_start_create.side_effect = APIError(
            "API request failed", 500
        )

        # call
        result = prepare_file(
            self.file, self.batch_pk, self.upload_session, mock_api_client
        )

        assert result == {
            "error": "API request failed",
            "status code": 500,
            "upload_session": 123,
        }


class TestPrepareFiles:
    @pytest.fixture(autouse=True)
    def setup(self):
        # Set up multiple files as dictionaries
        # self.file1 = {
        #     "name": "file1.txt",
        #     "size": 10000000,  # 10 MB
        #     "type": "text/plain",
        # }

        # self.file2 = {
        #     "name": "file2.txt",
        #     "size": 20000000,  # 20 MB
        #     "type": "text/plain",
        # }

        self.file1 = UploadSample(
            sample_name="name",
            upload_csv="test.csv",
            reads_1=Path("../samples"),
            reads_2=Path("../samples"),
            control="positive",
            instrument_platform="illumina",
            collection_date=date(2024, 12, 1),
            country="GBR",
            # reads_1_resolved_path="resolved_path",
            # reads_2_resolved_path="resolved_path2",
            # reads_1_dirty_checksum="dirty_checksum",
            # reads_2_dirty_checksum="dirty_checksum2",
            # reads_1_cleaned_path="cleaned_path",
            # reads_2_cleaned_path="cleaned_path2",
            # reads_1_pre_upload_checksum="pre_upload_checksum",
            # reads_2_pre_upload_checksum="pre_upload_checksum2",
            # reads_1_upload_file="reads_1",
            # reads_2_upload_file="reads_1",
            # reads_in=3,
            # reads_out=2,
            # reads_removed=1,
            file1_size=2,
            file2_size=4,
        )
        self.file2 = (
            UploadSample(
                sample_name="name2",
                upload_csv="test2.csv",
                reads_1=Path("../samples"),
                reads_2=Path("../samples"),
                control="positive",
                instrument_platform="illumina",
                collection_date=date(2024, 12, 1),
                country="GBR",
                # reads_1_resolved_path="resolved_path",
                # reads_2_resolved_path="resolved_path2",
                # reads_1_dirty_checksum="dirty_checksum",
                # reads_2_dirty_checksum="dirty_checksum2",
                # reads_1_cleaned_path="cleaned_path",
                # reads_2_cleaned_path="cleaned_path2",
                # reads_1_pre_upload_checksum="pre_upload_checksum",
                # reads_2_pre_upload_checksum="pre_upload_checksum2",
                # reads_1_upload_file="reads_1",
                # reads_2_upload_file="reads_1",
                # reads_in=3,
                # reads_out=2,
                # reads_removed=1,
                file1_size=3,
                file2_size=6,
            ),
        )

        # Set values for the batch and instrument
        self.batch_pk = 1
        self.instrument_code = "INST001"
        self.upload_session = 123

    def test_prepare_files_success(self, mock_api_client, mocker):
        # mock a successful credit check response
        mock_api_client.batches_samples_start_upload_session_create.return_value = {
            "status": 200,
            "data": {
                "upload_session": self.upload_session,
            },
        }

        # mock the check_if_file_is_in_sample function to return valid sample names
        mocker.patch(
            "pathogena.util.check_if_file_is_in_sample",
            side_effect=lambda sample_uploads, file: sample_uploads.get(file["name"]),
        )

        # set upload statuses of files assuming they're already present in the saple uploads
        # 1 complete and to be skipped in prepare files, 1 in progress
        sample_uploads = {
            "file1.txt": {
                "upload_status": "COMPLETE",
                "id": 1,
                "upload_id": "abc123",
                "total_chunks": 2,
            },
            "file2.txt": {
                "upload_status": "IN_PROGRESS",
                "id": 2,
                "upload_id": "def456",
                "total_chunks": 4,
            },
        }

        # mock prepare_file with successful preparation of new files
        mocker.patch(
            "pathogena.util.prepare_file",
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
                },
            ],
        )

        # list of files to pass to prepare_files
        files = [
            {"file": self.file1, "result": "POSITIVE"},
            {"file": self.file2, "result": "POSITIVE"},
        ]

        # call prepare_files
        result = prepare_files(
            self.batch_pk, self.instrument_code, files, mock_api_client, sample_uploads
        )

        assert len(result["files"]) == 1  # file1.txt is complete and so is skipped
        assert result["files"][0]["upload_id"] == "def456"  # file2 (in progress)
        assert (
            result["uploadSession"] == self.upload_session
        )  #  upload session is resumed

    def test_prepare_files_apierror(self, mock_api_client):
        # mock api error
        mock_api_client.batches_samples_start_upload_session_create.side_effect = (
            APIError("API request failed during credit check", 500)
        )

        # list of files to pass to prepare_files
        files = [
            {"file": self.file1, "result": "POSITIVE"},
            {"file": self.file2, "result": "POSITIVE"},
        ]

        # call
        result = prepare_files(
            self.batch_pk, self.instrument_code, files, mock_api_client
        )

        assert result == {
            "API error occurred when checking credits": "API request failed during credit check",
            "status code": 500,
        }


@pytest.fixture
def mock_upload_chunk(mocker):
    """Mocker fixture to simulate upload_chunk response

    Args:
        mocker: pytest-mock mocker fixture

    Returns:
        Mock object for httpx.Client.post
    """

    mocked_post = mocker.patch("pathogena.util.httpx.Client.post")
    mocked_get_access_token = mocker.patch(
        "pathogena.util.get_access_token", return_value="string"
    )

    def side_effect(url, **kwargs):
        # Expected data and headers
        expected_data = {
            "checksum": kwargs["data"]["checksum"],
            "dirty_checksum": kwargs["data"]["dirty_checksum"],
            "chunk_index": kwargs["data"]["chunk_index"],
        }
        assert kwargs["data"] == expected_data

        # Simulate successful upload with expected response
        return Response(
            status_code=200,
            json={
                "upload_status": "success",
                "sample_id": 0,
                "upload_id": "some_upload_id",
                "metrics": {
                    "chunks_received": 0,
                    "chunks_total": 0,
                    "upload_status": "success",
                    "percentage_complete": 0,
                    "upload_speed": 0,
                    "time_remaining": 0,
                    "estimated_completion_time": "2024-11-22T11:50:35.181Z",
                },
            },
        )

    mocked_post.side_effect = side_effect
    return mocked_post


def test_upload_chunk(mock_upload_chunk):
    batch_pk = 123
    host = "api.upload-dev.eit-pathogena.com"
    protocol = "https"
    checksum = "some_checksum"
    dirty_checksum = "another_checksum"
    chunk = b"file content"
    chunk_index = 0

    response = upload_chunk(
        batch_pk, host, protocol, checksum, dirty_checksum, chunk, chunk_index
    )

    assert response.json()["upload_status"] == "success"
    assert response.status_code == 200


class TestUploadChunks:
    @pytest.fixture(autouse=True)
    def setup(self, mocker):
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
        mocker.patch("pathogena.util.process_queue", return_value=None)

        # mock as_completed to simulate completed futures
        self.mock_end_upload = mocker.MagicMock()
        self.mock_end_upload.return_value = {
            "status": 200,
            "message": "Upload complete",
        }
        mocker.patch("pathogena.util.end_upload", self.mock_end_upload)

    # fixture for mock_upload_data
    @pytest.fixture
    def mock_upload_data(self, mocker):
        # mock relevant parts of UploadFileType class
        mock_upload_data = mocker.MagicMock(spec=UploadFileType)
        mock_upload_data.max_concurrent_chunks = 2
        mock_upload_data.batch_pk = self.batch_pk
        mock_upload_data.env = "api.upload-dev.eit-pathogena.com"
        mock_upload_data.on_progress = mocker.MagicMock()
        mock_upload_data.on_complete = mocker.MagicMock()
        return mock_upload_data

    # fixture for mock_file
    @pytest.fixture
    def mock_file(self, mocker):
        # mock relevant parts of SelectedFile class
        mock_file = mocker.MagicMock(spec=SelectedFile)
        mock_file.total_chunks = 4
        mock_file.upload_id = "file_123"
        mock_file.batch_id = self.batch_pk
        mock_file.file_data = [b"chunk1", b"chunk2", b"chunk3", b"chunk4"]
        return mock_file

    # fixture for mock_file_status
    @pytest.fixture
    def mock_file_status(self):
        return {}

    def test_upload_chunks_success(
        self, mock_upload_data, mock_file, mock_file_status, mocker
    ):
        # Mock upload_chunk to return a successful result
        mock_upload = mocker.MagicMock()
        mock_upload.result.return_value = mocker.MagicMock(
            status_code=200, text="OK", data={"metrics": "some_metrics"}
        )
        mocker.patch("pathogena.util.upload_chunk", return_value=mock_upload)

        # call
        upload_chunks(mock_upload_data, mock_file, mock_file_status)

        assert (
            mock_upload_data.on_progress.call_count == 4
        )  # called once for each chunk
        assert mock_upload_data.on_complete.called_once_with(
            mock_file.upload_id, mock_file.batch_id
        )  # on_complete called once
        # 4 chunks uploaded
        assert mock_file_status[mock_file.upload_id]["chunks_uploaded"] == 4
        assert (
            mock_file_status[mock_file.upload_id]["chunks_uploaded"]
            == mock_file.total_chunks
        )
        assert self.mock_end_upload.calledonce  # end_upload called once

    def test_upload_chunks_stop_on_400(
        self, mock_upload_data, mock_file, mock_file_status, mocker
    ):
        # mock the first chunk to succeed and the second to fail with a 400
        mock_upload_1 = mocker.MagicMock()
        mock_upload_1.result.return_value = mocker.MagicMock(
            status_code=200, text="OK", data={"metrics": "metrics_1"}
        )

        mock_upload_2 = mocker.MagicMock()
        mock_upload_2.result.return_value = mocker.MagicMock(
            status_code=400, text="Bad Request"
        )

        # mock upload_chunk to return the above mocks
        mocker.patch(
            "pathogena.util.upload_chunk", side_effect=[mock_upload_1, mock_upload_2]
        )

        # call
        upload_chunks(mock_upload_data, mock_file, mock_file_status)

        assert mock_upload_data.on_progress.call_count == 1  # only chunk 1 was uploaded
        assert (
            not self.mock_end_upload.called
        )  # end_upload should not be called as 2nd upload failed

    def test_upload_chunks_error_handling(
        self, mock_upload_data, mock_file, mock_file_status, mocker, caplog
    ):
        # mock the first chunk to raise an exception
        mock_upload_1 = mocker.MagicMock()
        mock_upload_1.result.side_effect = Exception("Some error")

        # mock upload_chunk to return the above mock
        mocker.patch("pathogena.util.upload_chunk", side_effect=[mock_upload_1])

        # call
        upload_chunks(mock_upload_data, mock_file, mock_file_status)

        assert (
            mock_upload_data.on_progress.call_count == 0
        )  # no chunk was successfully uploaded
        assert (
            not self.mock_end_upload.called
        )  # end_upload should not be called since there was an error
        assert (
            "Error uploading chunk 0 of batch 123: Some error" in caplog.text
        )  # eroor captures in logging


class TestUploadFiles:
    @pytest.fixture
    def mock_upload_data(self):
        """Fixture for mocked upload data."""
        # mocking UploadFileType with required attributes
        samples = [
            UploadSample(
                sample_name="name",
                upload_csv="test.csv",
                reads_1="path",
                reads_2="path2",
                control="positive",
                reads_1_resolved_path="resolved_path",
                reads_2_resolved_path="resolved_path2",
                reads_1_dirty_checksum="dirty_checksum",
                reads_2_dirty_checksum="dirty_checksum2",
                file1_size=2,
                file2_size=4,
            ),
            UploadSample(
                sample_name="name2",
                upload_csv="test2.csv",
                reads_1="path",
                reads_2="path2",
                control="positive",
                reads_1_resolved_path="resolved_path",
                reads_2_resolved_path="resolved_path2",
                reads_1_dirty_checksum="dirty_checksum",
                reads_2_dirty_checksum="dirty_checksum2",
                file1_size=3,
                file2_size=6,
            ),
        ]
        files = [
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
        ]
        return UploadFileType(
            access_token="access_token",
            batch_pk=123,
            env="env.com",
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
        return {"file1.txt": "pending", "file2.txt": "pending"}

    @pytest.fixture
    def mock_api_client(self, mocker):
        """Fixture for mocking the APIClient."""
        return mocker.MagicMock(spec=APIClient)

    def test_upload_files_success(
        self, mock_upload_data, mock_sample_uploads, mock_api_client, mocker
    ):
        # mock successful prepare files
        mock_prepare_files = mocker.patch(
            "pathogena.util.prepare_files",
            return_value={"files": [{"file": "file1.txt"}, {"file": "file2.txt"}]},
        )

        # mock successful upload_chunks
        mock_upload_chunks = mocker.patch(
            "pathogena.util.upload_chunks", return_value=None
        )

        # mock successful API client response
        mocker.patch.object(
            APIClient,
            "batches_samples_end_upload_session_create",
            return_value={"status": 200},
        )

        # call
        upload_files(
            mock_upload_data, "instrument_code", mock_api_client, mock_sample_uploads
        )

        # files were prepared
        mock_prepare_files.assert_called_once_with(
            batch_pk=mock_upload_data.batch_pk,
            instrument_code="instrument_code",
            files=mock_upload_data.files,
            api_client=mock_api_client,
            sample_uploads=mock_sample_uploads,
        )
        assert mock_upload_chunks.call_count == 2  # upload chunks called for each file
        APIClient.batches_samples_end_upload_session_create.assert_called_once_with(
            mock_upload_data.batch_pk, mock_upload_data
        )  # end session once

    def test_upload_files_prepare_api_error(
        self, mock_upload_data, mock_sample_uploads, mock_api_client, mocker
    ):
        # mock prepare_files with api error
        mock_prepare_files = mocker.patch(
            "pathogena.util.prepare_files",
            return_value={"API error occurred": "Some error"},
        )

        # call
        result = upload_files(
            mock_upload_data, "instrument_code", mock_api_client, mock_sample_uploads
        )

        mock_prepare_files.assert_called_once()  # prepare_files was called
        # result contains correct error message
        assert "API error occurred" in result
        assert result["API error occurred"] == "Some error"

    def test_upload_files_chunk_upload_error(
        self, mock_upload_data, mock_sample_uploads, mock_api_client, mocker, caplog
    ):
        ## mock successful prepare files
        mocker.patch(
            "pathogena.util.prepare_files",
            return_value={"files": [{"file": "file1.txt"}, {"file": "file2.txt"}]},
        )

        # mock upload_chunks with exception
        mock_upload_chunks = mocker.patch(
            "pathogena.util.upload_chunks", side_effect=Exception("Chunk upload error")
        )

        # mock successful API client response
        mocker.patch.object(
            APIClient,
            "batches_samples_end_upload_session_create",
            return_value={"status": 200},
        )

        # call
        result = upload_files(
            mock_upload_data, "instrument_code", mock_api_client, mock_sample_uploads
        )

        assert mock_upload_chunks.call_count == 2  # upload chunks called twice
        assert "Error uploading file" in caplog.text  # error is logged
