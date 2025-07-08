import json
import logging
from datetime import datetime, timedelta
from getpass import getpass

import httpx

from pathogena.client import env
from pathogena.constants import DEFAULT_HOST
from pathogena.log_utils import httpx_hooks


def authenticate(host: str = DEFAULT_HOST) -> None:
    """Requests a user auth token, writes to ~/.config/pathogena/tokens/<host>.json.

    Args:
        host (str): The host server. Defaults to DEFAULT_HOST.
    """
    logging.info(f"Authenticating with {host}")
    username = input("Enter your username: ")
    password = getpass(prompt="Enter your password (hidden): ")
    with httpx.Client(event_hooks=httpx_hooks) as client:
        response = client.post(
            f"{env.get_protocol()}://{host}/api/v1/auth/token",
            json={"username": username, "password": password},
            follow_redirects=True,
        )
    data = response.json()

    token_path = env.get_token_path(host)

    # Convert the expiry in seconds into a readable date, default token should be 7 days.
    one_week_in_seconds = 604800
    expires_in = data.get("expires_in", one_week_in_seconds)
    expiry = datetime.now() + timedelta(seconds=expires_in)
    data["expiry"] = expiry.isoformat()

    with token_path.open(mode="w") as fh:
        json.dump(data, fh)
    logging.info(f"Authenticated ({token_path})")


def check_authentication(host: str) -> None:
    """Check if the user is authenticated.

    Args:
        host (str): The host server.

    Raises:
        RuntimeError: If authentication fails.
    """
    with httpx.Client(event_hooks=httpx_hooks):
        response = httpx.get(
            f"{env.get_protocol()}://{host}/api/v1/batches",
            headers={"Authorization": f"Bearer {env.get_access_token(host)}"},
            follow_redirects=True,
        )
    if response.is_error:
        logging.error(f"Authentication failed for host {host}")
        raise RuntimeError(
            "Authentication failed. You may need to re-authenticate with `pathogena auth`"
        )
