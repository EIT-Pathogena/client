# upload_all chunks of a file
import logging
import math
import sys
import time
from itertools import chain
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_random_exponential

from pathogena.client.env import get_host, get_protocol, get_upload_host
from pathogena.constants import (
    DEFAULT_CHUNK_SIZE,
)
from pathogena.errors import APIError
from pathogena.types import (
    BatchUploadStatus,
    PreparedFile,
    Sample,
    UploadingFile,
    UploadSession,
)
from pathogena.util import get_access_token


class UploadAPIClient:
    """A class to handle API requests for batch uploads and related operations."""

    def __init__(
        self,
        base_url: str = get_upload_host(),
        client: httpx.Client | None = None,
        upload_session: int | None = None,
    ):
        """Initialize the APIClient with a base URL and an optional HTTP client.

        Args:
            base_url (str): The base URL for the API, e.g api.upload-dev.eit-pathogena.com
            client (httpx.Client | None): A custom HTTP client (Client) for making requests.
        """
        self.base_url = base_url
        self.client = client or httpx.Client()
        self.token = get_access_token(get_host())
        self.upload_session = upload_session

    def batches_create(
        self,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Creates a batch by making a POST request.

        Args:
            data (dict[str, Any] | None): Data to include in the POST request body.

        Returns:
            dict[str, Any]: The response JSON from the API.

        Raises:
            APIError: If the API returns a non-2xx status code.
        """
        url = f"{get_protocol()}://{self.base_url}/api/v1/batches"
        response = httpx.Response(httpx.codes.OK)
        try:
            response = self.client.post(
                url,
                json=data,
                headers={"Authorization": f"Bearer {self.token}"},
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise APIError(
                f"Failed to create: {response.text}", response.status_code
            ) from e

    def batches_samples_start_upload_session_create(
        self,
        batch_pk: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Starts a sample upload session by making a POST request to the backend.

        Args:
            batch_pk (str): The primary key of the batch.
            data (dict[str, Any] | None): Data to include in the POST request body.

        Returns:
            dict[str, Any]: The response JSON from the API.

        Raises:
            APIError: If the API returns a non-2xx status code.
        """
        url = f"{get_protocol()}://{self.base_url}/api/v1/batches/{batch_pk}/sample-files/start-upload-session/"
        try:
            response = self.client.post(
                url,
                json=data,
                headers={"Authorization": f"Bearer {self.token}"},
                follow_redirects=True,
            )
            self.upload_session = response.json().get("upload_session")

            response.raise_for_status()  # Raise an HTTPError for bad responses
            return response.json()
        except httpx.HTTPError as e:
            raise APIError(
                f"Failed to start upload session: {response.text}",
                response.status_code,
            ) from e

    def start_file_upload(
        self,
        file: PreparedFile,
        batch_id: str,
        sample_id: str,
        upload_session_id: int,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> UploadingFile:
        """Wraps batches_uploads_start_file_upload which calls `start-file-upload`.

        Handles:
        - creating the form to post data
        - checking the response code
        - logging and raising any API errors

        Args:
            file (PreparedFile): The file being uploaded.
            sample_id (str): The sample id for the file being uploaded.
            batch_pk (str): The batch id for the file being uploaded.
            upload_session_id (int): The upload session id.
            chunk_size (int, optional): The size of the chunks for the file. Defaults to DEFAULT_CHUNK_SIZE.

        Raises:
            APIError: If the response code is not 200.

        Returns:
            UploadingFile: The PreparedFile plus data returned from `start-file-upload`.
        """
        total_chunks = math.ceil(sys.getsizeof(file.data) / chunk_size)

        form_data = {
            "original_file_name": file.name,
            "total_chunks": total_chunks,
            "content_type": file.content_type,
            "sample_id": sample_id,
        }

        url = f"{get_protocol()}://{self.base_url}/api/v1/batches/{batch_id}/uploads/start/"
        try:
            response = self.client.post(
                url,
                json=form_data,
                headers={"Authorization": f"Bearer {self.token}"},
                follow_redirects=True,
            )
            if response.status_code != 200:
                raise APIError(
                    f"Failed to start batch upload: {response.text}",
                    response.status_code,
                )
            start_file_upload_json = response.json()
            return UploadingFile(
                file_id=start_file_upload_json.get("sample_file_id"),
                upload_id=start_file_upload_json.get("upload_id"),
                batch_id=batch_id,
                sample_id=start_file_upload_json.get("sample_id"),
                total_chunks=total_chunks,
                upload_session_id=upload_session_id,
                prepared_file=file,
            )
        except httpx.HTTPError as e:
            raise APIError(
                f"Failed to start batch upload: {response.text}",
                response.status_code,
            ) from e

    def batches_uploads_upload_chunk(
        self,
        batch_pk: int,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Starts a batch chunk upload session by making a POST request.

        Args:
            batch_pk (int): The primary key of the batch.
            data (dict[str, Any] | None): Data to include in the POST request body.

        Returns:
            dict[str, Any]: The response JSON from the API.

        Raises:
            APIError: If the API returns a non-2xx status code.
        """
        url = f"{get_protocol()}://{self.base_url}/api/v1/batches/{batch_pk}/uploads/upload-chunk/"
        try:
            response = self.client.post(
                url,
                json=data,
                headers={"Authorization": f"Bearer {self.token}"},
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise APIError(
                f"Failed to start batch chunk upload: {response.text}",
                response.status_code,
            ) from e

    def end_file_upload(
        self,
        batch_pk: int,
        data: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """End a batch upload by making a POST request.

        Args:
            batch_pk (int): The primary key of the batch.
            data (dict[str, Any] | None): Data to include in the POST request body.

        Returns:
            dict[str, Any]: The response JSON from the API.

        Raises:
            APIError: If the API returns a non-2xx status code.
        """
        url = (
            f"{get_protocol()}://{self.base_url}/api/v1/batches/{batch_pk}/uploads/end/"
        )
        try:
            response = self.client.post(
                url,
                json=data,
                headers={"Authorization": f"Bearer {self.token}"},
                follow_redirects=True,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPError as e:
            raise APIError(
                f"Failed to end batch upload: {response.text}", response.status_code
            ) from e

    def end_upload_session(
        self,
        batch_pk: str,
        upload_session_id: int | None = None,
    ) -> httpx.Response:
        """Ends a sample upload session by making a POST request to the backend.

        Args:
            batch_pk (str): The primary key of the batch.
            data (dict[str, Any] | None): Data to include in the POST request body.


        Returns:
            dict[str, Any]: The response JSON from the API.

        Raises:
            APIError: If the API returns a non-2xx status code.
        """
        if upload_session_id is not None:
            data = {"upload_session": upload_session_id}
        elif self.upload_session is not None:
            data = {"upload_session": self.upload_session}

        url = f"{get_protocol()}://{self.base_url}/api/v1/batches/{batch_pk}/sample-files/end-upload-session/"
        try:
            response = self.client.post(
                url,
                json=data,
                headers={"Authorization": f"Bearer {self.token}"},
                follow_redirects=True,
            )
            response.raise_for_status()  # Raise an HTTPError for bad responses
            return response
        except httpx.HTTPError as e:
            raise APIError(
                f"Failed to end upload session: {response.text}",
                response.status_code,
            ) from e

    def start_upload_session(
        self, batch_pk: str, prepared_samples: list[Sample[PreparedFile]]
    ):
        """Start upload session.

        Args:
            batch_pk (int): The id for the batch being created.
            prepared_samples (list[PreparedSample]): The list of prepared samples.

        Raises:
            APIError: If the API returns a non-2xx status code.
        """
        files = chain.from_iterable([sample.files for sample in prepared_samples])
        files_to_upload = [
            {
                "original_file_name": file.name,
                "file_size_in_kb": file.size,
                "control": file.control,
                "specimen_organism": file.specimen_organism,
            }
            for file in files
        ]

        form_details = {
            "files_to_upload": files_to_upload,
            "specimen_organism": files_to_upload[0].get("specimen_organism"),
        }

        try:
            session_response = self.batches_samples_start_upload_session_create(
                batch_pk=batch_pk, data=form_details
            )
            if not session_response["upload_session"]:
                # Log if the upload session could not be resumed
                logging.exception(
                    "Upload session cannot be resumed. Please create a new batch."
                )
                raise APIError(
                    "No upload session returned by the API.",
                    httpx.codes.INTERNAL_SERVER_ERROR,
                )

        except APIError as e:
            raise APIError(
                f"Error starting session: {str(e)}",
                e.status_code,
            ) from e

        upload_session_id = session_response["upload_session"]
        upload_session_name = session_response["name"]
        sample_summaries = session_response["sample_summaries"]

        return (upload_session_id, upload_session_name, sample_summaries)

    def get_batch_upload_status(
        self,
        batch_pk: str,
    ) -> BatchUploadStatus:
        """Starts an upload by making a POST request.

        Args:
            batch_pk (int): The primary key of the batch.
            data (dict[str, Any] | None): Data to include in the POST request body.

        Returns:
            dict[str, Any]: The response JSON from the API.

        Raises:
            APIError: If the API returns a non-2xx status code.
        """
        url = f"{get_protocol()}://{self.base_url}/api/v1/batches/{batch_pk}/state"
        try:
            response = self.client.get(
                url,
                headers={"Authorization": f"Bearer {self.token}"},
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise APIError(
                f"Failed to fetch batch status: {response.text}",
                response.status_code,
            ) from e

    @retry(
        wait=wait_random_exponential(multiplier=2, max=60), stop=stop_after_attempt(10)
    )
    def upload_chunk(
        self,
        batch_pk: int,
        protocol: str,
        chunk: bytes,
        chunk_index: int,
        upload_id: str,
    ) -> httpx.Response:
        """Upload a single file chunk.

        Args:
            batch_pk (int): ID of sample to upload
            host (str): pathogena host, e.g api.upload-dev.eit-pathogena.com
            protocol (str): protocol, default https
            chunk (bytes): File chunk to be uploaded
            chunk_index (int): Index representing what chunk of the whole
            sample file this chunk is from 0...total_chunks
            upload_id: the id of the upload session

        Returns:
            Response: The response object from the HTTP POST request conatining
            the status code and content from the server.
        """
        try:
            response = self.client.post(
                f"{protocol}://{self.base_url}/api/v1/batches/{batch_pk}/uploads/upload-chunk/",
                headers={"Authorization": f"Bearer {self.token}"},
                files={"chunk": chunk},  # Send the binary chunk
                data={
                    "chunk_index": chunk_index,
                    "upload_id": upload_id,
                },
                follow_redirects=True,
            )
            response.raise_for_status()
            return response
        except Exception as e:
            logging.error(
                f"Exception while uploading chunk {chunk_index} of batch {batch_pk}: {str(e), chunk[:10]} RESPONSE {response.status_code, response.headers, response.content}"
            )
            raise APIError(
                f"Failed to upload chunk {chunk_index} of batch {batch_pk}: {str(e), chunk[:10]} RESPONSE {response.status_code, response.headers, response.content}",
                response.status_code,
            ) from e
