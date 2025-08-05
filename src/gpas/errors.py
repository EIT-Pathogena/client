class InvalidPathError(Exception):
    """Custom exception for giving nice user errors around missing paths."""

    def __init__(self, message: str):
        """Constructor, used to pass a custom message to user.

        Args:
            message (str): Message about this path
        """
        self.message = message
        super().__init__(self.message)


class UnsupportedClientError(Exception):
    """Exception raised for unsupported client versions."""

    def __init__(self, this_version: str, current_version: str):
        """Raise this exception with a sensible message.

        Args:
            this_version (str): The version of installed version
            current_version (str): The version returned by the API
        """
        self.message = (
            f"\n\nThe installed client version ({this_version}) is no longer supported."
            " To update the client, please run:\n\n"
            "conda create -y -n gpas -c conda-forge -c bioconda hostile==1.1.0 && conda activate gpas && pip install --upgrade gpas"
        )
        super().__init__(self.message)


# Python errors for neater client errors
class AuthorizationError(Exception):
    """Custom exception for authorization issues. 401."""

    def __init__(self):
        """Initialize the AuthorizationError with a custom message."""
        self.message = "Authorization checks failed! Please re-authenticate with `gpas auth` and try again.\n"
        "If the problem persists please contact support (gpas.support@eit.org)."
        super().__init__(self.message)


class PermissionError(Exception):  # noqa: A001
    """Custom exception for permission issues. 403."""

    def __init__(self):
        """Initialize the PermissionError with a custom message."""
        self.message = (
            "You don't have access to this resource! Check logs for more details.\n"
            "Please contact support if you think you should be able to access this resource (gpas.support@eit.org)."
        )
        super().__init__(self.message)


class MissingError(Exception):
    """Custom exception for missing issues. (HTTP Status 404)."""

    def __init__(self):
        self.message = (
            "Resource not found! It's possible you asked for something which doesn't exist. "
            "Please double check that the resource exists."
        )
        super().__init__(self.message)


class ServerSideError(Exception):
    """Custom exception for all other server side errors. (HTTP Status 5xx)."""

    def __init__(self):
        self.message = (
            "We had some trouble with the server, please double check your command and try again in a moment.\n"
            "If the problem persists, please contact support (gpas.support@eit.org)."
        )
        super().__init__(self.message)


class InsufficientFundsError(Exception):
    """Custom exception for insufficient funds."""

    def __init__(self):
        self.message = (
            "Your account doesn't have enough credits to fulfil the number of Samples in your Batch. "
            "You can request more credits by contacting support (gpas.support@eit.org)."
        )
        super().__init__(self.message)


class APIError(Exception):
    """Custom exception for API errors."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code
