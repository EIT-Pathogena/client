import logging

import pytest
import httpx
from unittest.mock import patch

from gpas import lib
from gpas.util import UnsupportedClientException


@patch("httpx.Client.get")
@patch("gpas.__version__", "1.0.0")
def test_check_new_version_available(mock_get, caplog):
    caplog.set_level(logging.INFO)
    mock_get.return_value = httpx.Response(
        status_code=200, json={"info": {"version": "1.1.0"}}
    )
    lib.check_for_newer_version()
    assert "A new version of the GPAS CLI" in caplog.text


@patch("httpx.Client.get")
@patch("gpas.__version__", "1.0.0")
def test_check_no_new_version_available(mock_get, caplog):
    caplog.set_level(logging.INFO)
    mock_get.return_value = httpx.Response(
        status_code=200, json={"info": {"version": "1.0.0"}}
    )
    lib.check_for_newer_version()
    assert not caplog.text


@patch("httpx.Client.get")
@patch("gpas.__version__", "1.0.1")
def test_check_version_compatibility(mock_get):
    mock_get.return_value = httpx.Response(status_code=200, json={"version": "1.0.0"})
    lib.check_version_compatibility(host="dev.portal.gpas.world")


@patch("httpx.Client.get")
@patch("gpas.__version__", "1.0.0")
def test_fail_check_version_compatibility(mock_get, caplog):
    caplog.set_level(logging.INFO)
    mock_get.return_value = httpx.Response(status_code=200, json={"version": "1.0.1"})
    with pytest.raises(UnsupportedClientException):
        lib.check_version_compatibility(host="dev.portal.gpas.world")
        assert "is no longer supported" in caplog.text
