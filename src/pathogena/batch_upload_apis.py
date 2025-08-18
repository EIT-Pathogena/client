import os
from typing import Any

import httpx

from pathogena.constants import DEFAULT_HOST, DEFAULT_PROTOCOL, DEFAULT_UPLOAD_HOST
from pathogena.errors import APIError
from pathogena.util import get_access_token


def get_protocol() -> str:
    """Get the protocol to use for communication.

    Returns:
        str: The protocol (e.g., 'http', 'https').
    """
    if "PATHOGENA_PROTOCOL" in os.environ:
        protocol = os.environ["PATHOGENA_PROTOCOL"]
        return protocol
    else:
        return DEFAULT_PROTOCOL


def get_host(cli_host: str | None = None) -> str:
    """Return hostname using 1) CLI argument, 2) environment variable, 3) default value.

    Args:
        cli_host (str | None): The host provided via CLI argument.

    Returns:
        str: The resolved hostname.
    """
    return (
        cli_host
        if cli_host is not None
        else os.environ.get("PATHOGENA_HOST", DEFAULT_HOST)
    )


def get_upload_host(cli_host: str | None = None) -> str:
    """Return hostname using 1) CLI argument, 2) environment variable, 3) default value.

    Args:
        cli_host (str | None): The host provided via CLI argument.

    Returns:
        str: The resolved hostname.
    """
    return (
        cli_host
        if cli_host is not None
        else os.environ.get("PATHOGENA_UPLOAD_HOST", DEFAULT_UPLOAD_HOST)
    )


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
            batch_pk (int): The primary key of the batch.
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

    def batches_uploads_start_file_upload(
        self,
        batch_pk: str,
        data: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Starts an upload by making a POST request.

        Args:
            batch_pk (str): The primary key of the batch.
            data (dict[str, Any] | None): Data to include in the POST request body.

        Returns:
            dict[str, Any]: The response JSON from the API.

        Raises:
            APIError: If the API returns a non-2xx status code.
        """
        url = f"{get_protocol()}://{self.base_url}/api/v1/batches/{batch_pk}/uploads/start/"
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

    def batches_uploads_end_file_upload(
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

    def batches_samples_end_upload_session_create(
        self,
        batch_pk: str,
        upload_session: int | None = None,
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
        if upload_session is not None:
            data = {"upload_session": upload_session}
        else:
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
