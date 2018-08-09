import base64

from requests import HTTPError

from blobstash.base.client import Client
from blobstash.base.error import BlobStashError
from blobstash.base.iterator import BasePaginationIterator


class KVStoreError(BlobStashError):
    """Base error for the kvstore module."""


class KeyNotFoundError(KVStoreError):
    """Error raised when a key is not found."""


class KeyValue:
    def __init__(self, key, version, data=None, hash=None):
        self.key = key
        self.data = None
        if data:
            self.data = base64.b64decode(data)
        self.hash = hash
        self.version = version

    def __str__(self):
        return "KeyValue(key={!r}, version={})>".format(self.key, self.version)

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return hash("{}:{}".format(self.key, self.version))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        return hash(self) == hash(self)

    def __ne__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return not self.__eq__(other)


class KeysIterator(BasePaginationIterator):
    def __init__(self, client, **kwargs):
        super().__init__(client=client, path="/api/kvstore/keys", **kwargs)

    def parse_data(self, resp):
        raw_keys = resp["data"]
        keys = []
        for data in raw_keys:
            keys.append(KeyValue(**data))

        return keys


class KeyVersionsIterator(BasePaginationIterator):
    def __init__(self, client, key, **kwargs):
        self.key = key
        super().__init__(
            client=client, path="/api/kvstore/key/" + self.key + "/_versions", **kwargs
        )

    def parse_data(self, resp):
        raw_keys = resp["data"]
        keys = []
        for data in raw_keys:
            keys.append(KeyValue(**data))

        return keys


class KVStoreClient:
    def __init__(self, base_url=None, api_key=None, client=None):
        if client:
            self._client = client
            return

        self._client = Client(base_url=base_url, api_key=api_key)

    def put(self, key, data, ref="", version=-1):
        # XXX(tsileo): check with `ref` and `data` as None
        return KeyValue(
            **self._client.request(
                "POST",
                "/api/kvstore/key/" + key,
                data=dict(data=data, ref=ref, version=version),
            )
        )

    def get(self, key, version=None):
        try:
            return KeyValue(**self._client.request("GET", "/api/kvstore/key/" + key))
        except HTTPError as error:
            if error.response.status_code == 404:
                raise KeyNotFoundError
            raise

    def get_versions(self, key, cursor=None, limit=None):
        if isinstance(key, KeyValue):
            key = key.key
        try:
            return KeyVersionsIterator(self._client, key, cursor=cursor, limit=limit)
        except HTTPError as error:
            if error.response.status_code == 404:
                raise KeyNotFoundError
            raise

    def iter(self, cursor=None, limit=None, **kwargs):
        return KeysIterator(self._client, cursor=cursor, limit=limit, **kwargs)

    def __iter__(self):
        return KeysIterator(self._client)
