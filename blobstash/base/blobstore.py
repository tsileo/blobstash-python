from hashlib import blake2b

from requests import HTTPError

from blobstash.base.client import Client
from blobstash.base.error import BlobStashError
from blobstash.base.iterator import BasePaginationIterator


class BlobStoreError(BlobStashError):
    """Base error for the blobstore module."""


class BlobNotFoundError(BlobStoreError):
    """Error raised when a blob is not found."""


class Blob:
    def __init__(self, hash, data=None, size=None):
        self.hash = hash
        self.data = data or ""
        self.size = size
        if not self.size and self.data:
            self.size = len(self.data)

    @classmethod
    def from_data(cls, data):
        h = blake2b(digest_size=32)
        h.update(data)
        return cls(h.hexdigest(), data)

    def __hash__(self):
        return hash(self.hash)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        return self.hash == other.hash

    def __ne__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return not self.__eq__(other)

    def __repr__(self):
        return "Blob(hash={})".format(self.hash)

    def __str__(self):
        return self.__repr__()


class BlobsIterator(BasePaginationIterator):
    def __init__(self, client, **kwargs):
        super().__init__(client=client, path="/api/blobstore/blobs", **kwargs)

    def parse_data(self, resp):
        raw_blobs = resp["data"]
        blobs = []
        for blob in raw_blobs:
            blobs.append(Blob(**blob))

        return blobs


class BlobStoreClient:
    def __init__(self, base_url=None, api_key=None, client=None):
        if client:
            self._client = client
            return

        self._client = Client(base_url=base_url, api_key=api_key)

    def put(self, blob):
        files = {blob.hash: blob.data}
        resp = self._client.request(
            "POST", "/api/blobstore/upload", files=files, raw=True
        )
        resp.raise_for_status()

    def get(self, hash):
        resp = self._client.request(
            "GET", "/api/blobstore/blob/{}".format(hash), raw=True
        )
        try:
            resp.raise_for_status()
            return Blob(hash, resp.content)
        except HTTPError as error:
            if error.response.status_code == 404:
                raise BlobNotFoundError
            raise

    def iter(self, cursor=None, limit=None, per_page=None, **kwargs):
        return BlobsIterator(
            self._client, cursor=cursor, limit=limit, per_page=per_page, **kwargs
        )

    def __iter__(self):
        return BlobsIterator(self._client)
