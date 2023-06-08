from urllib.parse import urljoin

import httpx

from app.common_tags import ONADATA_USER_ENDPOINT


class FailedExternalRequest(Exception):
    pass


def retrieve_onadata_profile(access_token: str, base_url: str) -> dict:
    """
    Retrieves the OnaData profile using the provided access token.
    """
    resp = httpx.get(
        url=urljoin(base_url, ONADATA_USER_ENDPOINT),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )

    if resp.status_code != 200:
        raise FailedExternalRequest(resp.text)
    else:
        return resp.json()
