import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from httpx import Response

from pathogena.util import upload_chunk, upload_file_as_chunks


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


def test_upload_file_as_chunks(mocker):
    # Patch upload_chunk in the same module where upload_file_as_chunks is defined
    mocked_upload_chunk = mocker.patch("pathogena.util.upload_chunk")

    # Mock a sucessful response
    mocked_upload_chunk.return_value = mocker.Mock(status_code=200)

    # Mockchunk_file to avoid actual file operations
    mocker.patch("pathogena.util.chunk_file", return_value=[b"chunk1", b"chunk2"])

    # set values for upload_file_as_chunks
    batch_pk = 123
    file_path = "test_file.txt"
    host = "testhost.com"
    protocol = "https"
    checksum = "dummy_checksum"
    dirty_checksum = "dummy_dirty_checksum"

    # Call the function
    upload_file_as_chunks(
        batch_pk=batch_pk,
        file_path=Path(file_path),
        host=host,
        protocol=protocol,
        checksum=checksum,
        dirty_checksum=dirty_checksum,
    )

    # Verify that upload_chunk was called correctly
    assert mocked_upload_chunk.call_count == 2  # Two chunks expected
    mocked_upload_chunk.assert_any_call(
        batch_pk,
        host,
        protocol,
        checksum,
        dirty_checksum,
        b"chunk1",
        0,
    )
    mocked_upload_chunk.assert_any_call(
        batch_pk,
        host,
        protocol,
        checksum,
        dirty_checksum,
        b"chunk2",
        1,
    )


def test_upload_file_as_chunks_error(mocker):
    # Patch upload_chunk to avoid actual uploading
    mocked_upload_chunk = mocker.patch("pathogena.util.upload_chunk")

    # Mock a sucessful and unsucessful response
    mocked_upload_chunk.side_effect = [
        mocker.Mock(Response == 200),
        Exception("Mocked error for chunk 2"),
    ]

    # Mock chunk_file to avoid actual file operations
    mocker.patch("pathogena.util.chunk_file", return_value=[b"chunk1", b"chunk2"])

    # Mock logging
    mocked_logging = mocker.patch("pathogena.util.logging.error")

    # set values for upload_file_as_chunks
    batch_pk = 123
    file_path = "test_file.txt"
    host = "testhost.com"
    protocol = "https"
    checksum = "dummy_checksum"
    dirty_checksum = "dummy_dirty_checksum"

    # Call the function
    try:  # noqa: SIM105
        upload_file_as_chunks(
            batch_pk=batch_pk,
            file_path=Path(file_path),
            host=host,
            protocol=protocol,
            checksum=checksum,
            dirty_checksum=dirty_checksum,
        )
    except Exception:
        pass  # Catch the exception and allow the test to continue

    assert mocked_upload_chunk.call_count == 2
    mocked_logging.assert_called_with("Error uploading file chunk:{e}")


def test_upload_file_as_chunks_threading(tmp_path, mocker):
    # Patch upload_chunk to avoid actual uploading
    mocked_upload_chunk = mocker.patch("pathogena.util.upload_chunk")

    # Mock a sucessful response
    mocked_upload_chunk.side_effect = [mocker.Mock(Response == 200)]

    # Mock chunk_file to avoid actual file operations
    mocked_chunked_file = mocker.patch(
        "pathogena.util.chunk_file",
        return_value=[b"chunk1", b"chunk2", b"chunk3", b"chunk4", b"chunk5", b"chunk6"],
    )

    original_submitter = ThreadPoolExecutor.submit
    active_thread_count = []

    # wrap submittion so that it counts the number of active threads
    def custom_submitter(self, fn, *args, **kwargs):
        active_thread_count.append(len(self._threads))
        return original_submitter(self, fn, *args, **kwargs)

    # mock the ThreadPoolExecutor.submit
    mocker.patch.object(ThreadPoolExecutor, "submit", custom_submitter)

    # set values for upload_file_as_chunks
    batch_pk = 123
    file_path = "test_file.txt"
    host = "testhost.com"
    protocol = "https"
    checksum = "dummy_checksum"
    dirty_checksum = "dummy_dirty_checksum"

    with mocker.patch(
        "pathogena.util.ThreadPoolExecutor",
        wraps=ThreadPoolExecutor,
    ) as mock_executer:
        upload_file_as_chunks(
            batch_pk, Path(file_path), host, protocol, checksum, dirty_checksum
        )

    max_concurrent_chunks = int(os.getenv("MAX_CONCURRENT_CHUNKS", 5))

    ## maximum number of active threads cannot exceed max concurrent chunks
    assert max(active_thread_count) <= max_concurrent_chunks
    ## assert that upload_chunk was called once for all of the returned file chunks
    assert mocked_upload_chunk.call_count == len(mocked_chunked_file.return_value)
    ## assert maximum number of active threads cannot exceed number of generated file chunks
    assert max(active_thread_count) <= len(mocked_chunked_file.return_value)
