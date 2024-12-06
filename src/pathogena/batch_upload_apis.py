from typing import Any

import requests


class APIError(Exception):
    """Custom exception for API errors."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class APIClient:
    """A class to handle API requests for batch uploads and related operations."""

    def __init__(self, base_url: str, client: requests.Session | None = None):
        """Initialize the APIClient with a base URL and an optional HTTP client.

        Args:
            base_url (str): The base URL for the API, e.g api.upload-dev.eit-pathogena.com
            client (requests.Session | None): A custom HTTP client (session) for making requests.
        """
        self.base_url = base_url
        self.client = client or requests.Session()

    # create batch
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
        url = f"{self.base_url}/api/v1/batches/"
        try:
            response = self.client.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            raise APIError(
                f"Failed to create: {e.response.text}", response.status_code
            ) from e

    ## start upload session for a batches samples
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
        url = f"{self.base_url}/api/v1/batches/{batch_pk}/samples/start-upload-session/"

        try:
            response = self.client.post(url, json=data)
            response.raise_for_status()  # Raise an HTTPError for bad responses
            return response.json()
        except requests.HTTPError as e:
            raise APIError(
                f"Failed to start upload session: {e.response.text}",
                response.status_code,
            ) from e

    # start batch upload
    def batches_uploads_start_create(
        self,
        batch_pk: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Starts a upload by making a POST request.

        Args:
            batch_pk (str): The primary key of the batch.
            data (dict[str, Any] | None): Data to include in the POST request body.

        Returns:
            dict[str, Any]: The response JSON from the API.

        Raises:
            APIError: If the API returns a non-2xx status code.
        """
        url = f"{self.base_url}/api/v1/batches/{batch_pk}/uploads/start/"
        try:
            response = self.client.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            raise APIError(
                f"Failed to start batch upload: {e.response.text}", response.status_code
            ) from e

    # start a chunking session
    def batches_uploads_upload_chunk_create(
        self,
        batch_pk: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Starts a batch chunk upload session by making a POST request.

        Args:
            batch_pk (str): The primary key of the batch.
            data (dict[str, Any] | None): Data to include in the POST request body.

        Returns:
            dict[str, Any]: The response JSON from the API.

        Raises:
            APIError: If the API returns a non-2xx status code.
        """
        url = f"{self.base_url}/api/v1/batches/{batch_pk}/uploads/upload-chunk/"
        try:
            response = self.client.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            raise APIError(
                f"Failed to start batch chunk upload: {e.response.text}",
                response.status_code,
            ) from e

    # end batch upload
    def batches_uploads_end_create(
        self,
        batch_pk: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """End a batch upload by making a POST request.

        Args:
            batch_pk (str): The primary key of the batch.
            data (dict[str, Any] | None): Data to include in the POST request body.

        Returns:
            dict[str, Any]: The response JSON from the API.

        Raises:
            APIError: If the API returns a non-2xx status code.
        """
        url = f"{self.base_url}/api/v1/batches/{batch_pk}/uploads/end/"
        try:
            response = self.client.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            raise APIError(
                f"Failed to end batch upload: {e.response.text}", response.status_code
            ) from e

    ## end upload session for a batches samples
    def batches_samples_end_upload_session_create(
        self,
        batch_pk: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ends a sample upload session by making a POST request to the backend.

        Args:
            batch_pk (str): The primary key of the batch.
            data (dict[str, Any] | None): Data to include in the POST request body.


        Returns:
            dict[str, Any]: The response JSON from the API.

        Raises:
            APIError: If the API returns a non-2xx status code.
        """
        url = f"{self.base_url}/api/v1/batches/{batch_pk}/samples/end-upload-session/"

        try:
            response = self.client.post(url, json=data)
            response.raise_for_status()  # Raise an HTTPError for bad responses
            return response.json()
        except requests.HTTPError as e:
            raise APIError(
                f"Failed to end upload session: {e.response.text}", response.status_code
            ) from e
