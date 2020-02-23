"""BlobStash client."""
import json
import os
from urllib.parse import urljoin

import requests

DEFAULT_BASE_URL = "http://localhost:8050"


class Client:
    """Basic client for API-specific client to build upon."""

    def __init__(self, base_url=None, api_key=None, json_encoder=json.JSONEncoder):
        self.base_url = base_url or os.getenv("BLOBSTASH_BASE_URL", DEFAULT_BASE_URL)
        self.api_key = api_key or os.getenv("BLOBSTASH_API_KEY")
        self.json_encoder = json_encoder

    def request(self, verb: str, path: str, **kwargs):
        """Helper for making authenticated request to BlobStash."""
        raw = kwargs.pop("raw", False)
        json_data = kwargs.pop("json", None)
        if json_data:
            kwargs["data"] = json.dumps(json_data, cls=self.json_encoder)
            headers = kwargs.get("headers", {})
            headers["Content-Type"] = "application/json"
            kwargs["headers"] = headers

        if self.api_key:
            kwargs["auth"] = ("", self.api_key)

        r = requests.request(verb, urljoin(self.base_url, path), **kwargs)
        if raw:
            return r

        r.raise_for_status()
        if r.status_code != 204:
            return r.json()
