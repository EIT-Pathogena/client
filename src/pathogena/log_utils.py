import logging
import sys
from types import TracebackType

import httpx

from pathogena.errors import (
    AuthorizationError,
    InsufficientFundsError,
    MissingError,
    ServerSideError,
)


def configure_debug_logging(debug: bool) -> None:
    """Configure logging for debug mode.

    Args:
        debug (bool): Whether to enable debug logging.
    """
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Debug logging enabled")
    else:
        logging.getLogger().setLevel(logging.INFO)
        # Supress tracebacks on exceptions unless in debug mode.
        sys.excepthook = exception_handler


def exception_handler(
    exception_type: type[BaseException], exception: Exception, _traceback: TracebackType
) -> None:
    """Handle uncaught exceptions by logging them.

    Args:
        exc_type (type): Exception type.
        exc_value (BaseException): Exception instance.
        exc_traceback (TracebackType): Traceback object.
    """
    logging.error(f"{exception_type.__name__}: {exception}")


def log_request(request: httpx.Request) -> None:
    """Log HTTP request details.

    Args:
        request (httpx.Request): The HTTP request object.
    """
    logging.debug(f"Request: {request.method} {request.url}")


def log_response(response: httpx.Response) -> None:
    """Log HTTP response details.

    Args:
        response (httpx.Response): The HTTP response object.
    """
    if response.is_error:
        request = response.request
        response.read()
        message = response.json().get("message")
        logging.error(f"{request.method} {request.url} ({response.status_code})")
        logging.error(message)


def raise_for_status(response: httpx.Response) -> None:
    """Raise an exception for HTTP error responses.

    Args:
        response (httpx.Response): The HTTP response object.

    Raises:
        httpx.HTTPStatusError: If the response contains an HTTP error status.
    """
    if response.is_error:
        response.read()
        if response.status_code == 401:
            logging.error("Have you tried running `pathogena auth`?")
            raise AuthorizationError()
        elif response.status_code == 402:
            raise InsufficientFundsError()
        elif response.status_code == 403:
            raise PermissionError()
        elif response.status_code == 404:
            raise MissingError()
        elif response.status_code // 100 == 5:
            raise ServerSideError()

    # Default to httpx errors in other cases
    response.raise_for_status()


httpx_hooks = {"request": [log_request], "response": [log_response, raise_for_status]}
