from blobstash.base.test_utils import BlobStash
from blobstash.docstore import DocStoreClient, Q


def test_docstore():
    b = BlobStash()
    b.cleanup()
    try:
        b.run()
        client = DocStoreClient(api_key='123')

        col1 = client.col1

        for i in range(10):
            col1.insert({'lol': i+1})

        col2 = client.col2

        COL = 'hello'
        DOCS_COUNT = 1000
        docs = []
        for i in range(DOCS_COUNT):
            doc = dict(hello=i)
            resp = col2.insert(doc)
            docs.append(doc)

        for doc in docs:
            rdoc = col2.get_by_id(doc['_id'])
            assert rdoc == doc

        rdocs = []
        for rdoc in col2.query():
            rdocs.append(rdoc)

        assert rdocs == docs[::-1]

        col3 = client.col3

        for i in range(50):
            col3.insert({'i': i, 'nested': {'i': i}, 'l': [True, i]})

        assert len(list(col3.query(Q['nested']['i'] >= 25))) == 25

        assert sorted(['col1', 'col2', 'col3']) == sorted([c.name for c in client.collections()])

    finally:
        b.shutdown()
        b.cleanup()
