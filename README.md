# BlobStash Python Client

[![builds.sr.ht status](https://builds.sr.ht/~tsileo/blobstash-python.svg)](https://builds.sr.ht/~tsileo/blobstash-python?)
&nbsp; &nbsp; [![PyPI](https://img.shields.io/pypi/v/blobstash-docstore.svg)](https://pypi.python.org/pypi/blobstash)
&nbsp; &nbsp; [![PyPI](https://img.shields.io/pypi/pyversions/blobstash-docstore.svg)](https://pypi.python.org/pypi/blobstash)
&nbsp; &nbsp; [![License](http://img.shields.io/badge/license-MIT-red.svg?style=flat)](https://git.sr.ht/~tsileo/blobstash-python/tree/master/LICENSE)
&nbsp; &nbsp; <a href="https://github.com/ambv/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>

Client for [BlobStash](https://git.sr.ht/~tsileo/blobstash).

## Examples

### Document Store

```python
>>> from blobstash.docstore import DocStoreClient, Q
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
# Native Python query using Q
>>> for doc in col.query(Q['key'] == 10):
...     print(doc)
{'k1': True, 'k2': None, 'key': 10, 'l': [1, 2, 'c'], '_id': <blobstash.docstore.ID _id='14d854f6e9ee37a9cd8c1ffc'>}
>>> for doc in col.query(Q['key'] > 10):
...     print(doc)

>>> for doc in col.query():
...     print(doc)
{'k1': True, 'k2': None, 'key': 10, 'l': [1, 2, 'c'], '_id': <blobstash.docstore.ID _id='14d854f6e9ee37a9cd8c1ffc'>}
>>> for doc in col.query(Q['l'].contains(1)):
...     print(doc)
{'k1': True, 'k2': None, 'key': 10, 'l': [1, 2, 'c'], '_id': <blobstash.docstore.ID _id='14d854f6e9ee37a9cd8c1ffc'>}
>>> for doc in col.query(Q['l'][0] == 1):
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
