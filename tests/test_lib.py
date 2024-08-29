import logging

import pytest
import httpx
from unittest.mock import patch

from pathogena import lib
from pathogena.util import UnsupportedClientException


@patch("httpx.Client.get")
@patch("pathogena.__version__", "1.0.0")
def test_check_new_version_available(mock_get, caplog):
    caplog.set_level(logging.INFO)
    mock_get.return_value = httpx.Response(
        status_code=200, json={"info": {"version": "1.1.0"}}
    )
    lib.check_for_newer_version()
    assert "A new version of the EIT Pathogena CLI" in caplog.text


@patch("httpx.Client.get")
@patch("pathogena.__version__", "1.0.0")
def test_check_no_new_version_available(mock_get, caplog):
    caplog.set_level(logging.INFO)
    mock_get.return_value = httpx.Response(
        status_code=200, json={"info": {"version": "1.0.0"}}
    )
    lib.check_for_newer_version()
    assert not caplog.text


@patch("httpx.Client.get")
@patch("pathogena.__version__", "1.0.1")
def test_check_version_compatibility(mock_get, test_host):
    mock_get.return_value = httpx.Response(status_code=200, json={"version": "1.0.0"})
    lib.check_version_compatibility(host=test_host)


@patch("httpx.Client.get")
@patch("pathogena.__version__", "1.0.0")
def test_fail_check_version_compatibility(mock_get, test_host, caplog):
    caplog.set_level(logging.INFO)
    mock_get.return_value = httpx.Response(status_code=200, json={"version": "1.0.1"})
    with pytest.raises(UnsupportedClientException):
        lib.check_version_compatibility(host=test_host)
        assert "is no longer supported" in caplog.text


@patch("httpx.Client.get")
@patch("pathogena.lib.get_access_token")
def test_get_balance(mock_token, mock_get, caplog):
    caplog.set_level(logging.INFO)
    mock_token.return_value = "fake_token"
    mock_get.return_value = httpx.Response(status_code=200, text="1000")
    lib.get_credit_balance(host="fake_host")
    assert "Your remaining account balance is 1000 credits" in caplog.text


@patch("httpx.Client.get")
@patch("pathogena.lib.get_access_token")
def test_get_balance_failure(mock_token, mock_client_get, caplog):
    mock_token.return_value = "fake_token"
    mock_client_get.return_value = httpx.Response(status_code=402)
    lib.get_credit_balance(host="fake_host")
    assert (
        "Your account doesn't have enough credits to fulfil the number of Samples in your Batch."
        in caplog.text
    )
