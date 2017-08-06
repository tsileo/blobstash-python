# BlobStash Python DocStore

Python 3.4+ only.

Client for [BlobStash](https://github.com/tsileo/blobstash) JSON document store.

## Examples

```python
>>> from blobstash.docstore import DocStoreClient, Path
>>> client = DocStoreClient(api_key='123')
>>> col = client.my_collection
>>> col
<blobstash.docstore.Collection name='my_collection'>
>>> # Insert data
>>> k = col.insert({'key': 10, 'k1': True, 'k2': None, 'l': [1, 2, 'c']})
>>> k
<blobstash.docstore.ID _id='14d854f6e9ee37a9cd8c1ffc'>
>>> # Get a single document
>>> col.get_by_id(k)
{'_id': <blobstash.docstore.ID _id='14d854f6e9ee37a9cd8c1ffc'>,
 'k1': True,
 'k2': None,
 'key': 10,
 'l': [1, 2, 'c']}
>>> col.get_by_id('14d854f6e9ee37a9cd8c1ffc')
{'_id': <blobstash.docstore.ID _id='14d854f6e9ee37a9cd8c1ffc'>,
 'k1': True,
 'k2': None,
 'key': 10,
 'l': [1, 2, 'c']}
>>> # Using Path, you can make query using basic dot notation and python values directly
>>> for doc in col.query(Path('key') == 10):
...     print(doc)
{'k1': True, 'k2': None, 'key': 10, 'l': [1, 2, 'c'], '_id': <blobstash.docstore.ID _id='14d854f6e9ee37a9cd8c1ffc'>}
>>> for doc in col.query(Path('key') > 10):
...     print(doc)

>>> for doc in col.query():
...     print(doc)
{'k1': True, 'k2': None, 'key': 10, 'l': [1, 2, 'c'], '_id': <blobstash.docstore.ID _id='14d854f6e9ee37a9cd8c1ffc'>}
>>> for doc in col.query(Path('l').contains(1)):
...     print(doc)
{'k1': True, 'k2': None, 'key': 10, 'l': [1, 2, 'c'], '_id': <blobstash.docstore.ID _id='14d854f6e9ee37a9cd8c1ffc'>}
>>> for doc in col.query(Path('l[0]') == 1):
...     print(doc)
{'k1': True, 'k2': None, 'key': 10, 'l': [1, 2, 'c'], '_id': <blobstash.docstore.ID _id='14d854f6e9ee37a9cd8c1ffc'>}
>>> # Raw Lua query
>>> # 1. in shortcut mode
>>> for doc in col.query("doc.k1 == true and doc.key ~= nil"):
...     print(doc)
{'k1': True, 'k2': None, 'key': 10, 'l': [1, 2, 'c'], '_id': <blobstash.docstore.ID _id='14d854f6e9ee37a9cd8c1ffc'>}
>>> # 2. full Lua script
>>> from blobstash.docstore.query import LuaScript
>>> script = LuaScript("""
... return function(doc)
...   if doc.key == 10 then
...     return true
...   end
...   return false
... end
... """)
>>> for doc in col.query(script):
...     print(doc)
{'k1': True, 'k2': None, 'key': 10, 'l': [1, 2, 'c'], '_id': <blobstash.docstore.ID _id='14d854f6e9ee37a9cd8c1ffc'>}
```

## LICENSE

MIT
