from blobstash.base.test_utils import BlobStash
from blobstash.docstore import DocStoreClient


def test_docstore():
    b = BlobStash()
    b.cleanup()
    try:
        b.run()
        client = DocStoreClient(api_key='123')
    finally:
        b.shutdown()
        b.cleanup()
