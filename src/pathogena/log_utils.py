import logging
import sys
from collections.abc import Callable, Mapping
from types import TracebackType
from typing import Any

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
    exception_type: type[BaseException],
    exception: BaseException,
    _traceback: TracebackType | None,
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
        if response.status_code == httpx.codes.UNAUTHORIZED:
            logging.error("Have you tried running `pathogena auth`?")
            raise AuthorizationError()
        elif response.status_code == httpx.codes.PAYMENT_REQUIRED:
            raise InsufficientFundsError()
        elif response.status_code == httpx.codes.FORBIDDEN:
            raise PermissionError()
        elif response.status_code == httpx.codes.NOT_FOUND:
            raise MissingError()
        elif response.status_code == httpx.codes.UPGRADE_REQUIRED:
            return None
        elif response.status_code >= 500:
            raise ServerSideError()

    # Default to httpx errors in other cases
    response.raise_for_status()


httpx_hooks: Mapping[str, list[Callable[..., Any]]] = {
    "request": [log_request],
    "response": [log_response, raise_for_status],
}
