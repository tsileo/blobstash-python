import os

import pytest

from blobstash.base.blobstore import Blob, BlobNotFoundError, BlobStoreClient
from blobstash.base.client import Client
from blobstash.base.kvstore import KVStoreClient
from blobstash.base.test_utils import BlobStash


def test_test_utils():
    """Ensure the BlobStash utils can spawn a server."""
    b = BlobStash()
    b.cleanup()
    try:
        b.run()
        c = Client()
        resp = c.request("GET", "/", raw=True)
        assert resp.status_code == 404
    finally:
        b.shutdown()
        b.cleanup()


def test_blobstore_client():
    """Ensure the BlobStash utils can spawn a server."""
    b = BlobStash()
    b.cleanup()
    try:
        b.run()
        client = BlobStoreClient(api_key="123")

        assert len(list(client)) == 0
        assert len(list(client.iter())) == 0

        # try a blob that does not exist
        with pytest.raises(BlobNotFoundError):
            client.get("0" * 64)

        # (blake2b 256 bits for an empty string)
        expected_empty_hash = (
            "0e5751c026e543b2e8ab2eb06099daa1d1e5df47778f7787faab45cdf12fe3a8"
        )

        empty_blob = Blob.from_data(b"")
        assert empty_blob.hash == expected_empty_hash
        client.put(empty_blob)

        fetched_empty_blob = client.get(expected_empty_hash)
        assert empty_blob == fetched_empty_blob

        blobs = [empty_blob]

        for i in range(1000 - len(blobs)):
            blob = Blob.from_data(os.urandom(1024 * 8))
            client.put(blob)
            blobs.append(blob)

        def by_hash(blob):
            return blob.hash

        blobs = sorted(blobs, key=by_hash)
        fetched_blobs = sorted([cblob for cblob in client], key=by_hash)
        assert len(fetched_blobs) == len(blobs)

        for i, blob_ref in enumerate(fetched_blobs):
            assert blob_ref.hash == blobs[i].hash
            blob = client.get(blob_ref.hash)
            assert blob.data == blobs[i].data

    finally:
        b.shutdown()
        b.cleanup()


def test_kvstore_client():
    """Ensure the BlobStash utils can spawn a server."""
    b = BlobStash()
    b.cleanup()
    try:
        b.run()
        client = KVStoreClient(api_key="123")

        KV_COUNT = 10
        KV_VERSIONS_COUNT = 100

        keys = {}
        for x in range(KV_COUNT):
            key = "k{}".format(x)
            if key not in keys:
                keys[key] = []
            for y in range(KV_VERSIONS_COUNT):
                val = "value.{}.{}".format(x, y)
                kv = client.put("k{}".format(x), val, version=y + 1)
                keys[key].append(kv)

        for key in keys.keys():
            kv = client.get(key)
            assert kv == keys[key][-1]
            versions = list(client.get_versions(key))
            assert len(versions) == len(keys[key])
            for i, kv in enumerate(versions):
                assert kv == keys[key][KV_VERSIONS_COUNT - (1 + i)]

        b.shutdown()
        for f in [
            "blobstash_data/.80a3e998d3248e3f44c5c608fd8dc813e00567a3",
            "blobstash_data/.82481ffa006d3077c01fb135f375eaa25816881c",
            "blobstash_data/.e7ecafda402e922e0fcefb3741538bd152c35405",
            "blobstash_data/vkv",
        ]:
            os.unlink(f)

        b.run(reindex=True)

        for key in keys.keys():
            kv = client.get(key)
            assert kv == keys[key][-1]
            versions = list(client.get_versions(key))
            assert len(versions) == KV_VERSIONS_COUNT
            for i, kv in enumerate(versions):
                assert kv == keys[key][KV_VERSIONS_COUNT - (1 + i)]

        rkeys = list(client.iter())
        for kv in rkeys:
            assert kv == keys[kv.key][-1]

    finally:
        print("done")
        b.shutdown()
        b.cleanup()
