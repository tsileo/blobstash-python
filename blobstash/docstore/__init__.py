from urllib.parse import urljoin
from copy import deepcopy
from datetime import datetime
from datetime import timezone

from blobstash.driver.client import Client
from blobstash.docstore.query import Path  # noqa: unused-import  # make it accessible
from blobstash.docstore.query import LogicalOperator
from blobstash.docstore.query import Not
from blobstash.docstore.query import LuaScript

import requests
import jsonpatch


# TODO(tsileo): cache all the doc for generating JSON patch on update (subclass dict to cache it only
# on edit?
_DOC_CACHE = {}


class _Document(dict):
    """Document is a dict subclass for document returned by the API, keep track of the ETag, and the document for the
    JSON Patch generation if needed."""

    def __setitem__(self, key, val):
        _id = self.get('_id')
        if _id is None:
            raise Exception('missing _id')


        if _id not in _DOC_CACHE:
            doc = self.copy()
            del doc['_id']
            _DOC_CACHE[_id] = deepcopy(doc)

        dict.__setitem__(self, key, val)

    def __repr__(self):
        dictrepr = dict.__repr__(self)
        return '%s(%s)' % (type(self).__name__, dictrepr)


class ID:
    """ID holds the document ID along with metadata."""

    def __init__(self, data):
        self._id = data.get('_id')
        self._created = data.get('_created')
        self._updated = data.get('_updated')
        self._hash = data.get('_hash')

    @classmethod
    def inject(cls, data):
        """Extracts ID infos from the document special keys and remove them, replacing
        `_id` with an instance of `ID`."""
        doc_id = cls(data)
        if doc_id._id:
            del data['_id']
        if doc_id._created:
            del data['_created']
        if doc_id._updated:
            del data['_updated']
        if doc_id._hash:
            del data['_hash']
        data['_id'] = doc_id
        return doc_id

    def hash(self):
        return self._hash

    def id(self):
        return self._id

    def created(self):
        return self._parse_dt(self._created)

    def updated(self):
        return self._parse_dt(self._updated)

    def _parse_dt(self, dt_str):
        if dt_str is None:
            return

        dt = datetime.strptime(dt_str, '%Y-%m-%dT%H:%M:%SZ')
        dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone()

    def __hash__(self):
        return hash((self._hash, self._id))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        return (self._hash, self._id) == (other.hash(), other.id())

    def __ne__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return not self.__eq__(other)

    def __repr__(self):
        return '<blobstash.docstore.ID _id={!r}>'.format(self._id)

    def __str__(self):
        return self._id


class Cursor:
    """Cursor is the query iterator, take care of going through the pagination."""

    def __init__(self, collection, query, resp, limit=None):
        self._collection = collection
        self._query = query
        self._limit = limit
        self._parse_resp(resp)

    def _parse_resp(self, resp):
        self.docs = []
        for raw_doc in resp['data']:
            ID.inject(raw_doc)
            self.docs.append(_Document(raw_doc))

        pagination = resp['pagination']
        self.has_more = pagination['has_more']
        self.cursor = pagination['cursor']

    def __iter__(self):
        return self

    def __next__(self):
        try:
            doc = self.docs.pop(0)
            return doc
        except IndexError:
            if not self.has_more:
                raise StopIteration
            resp = self._collection._query(self._query, cursor=self.cursor)
            self._parse_resp(resp)
            return next(self)

    def __repr__(self):
        return '<blobstash.docstore.Cursor collection={!r}>'.format(self._collection.name)

    def __str__(self):
        return self.__repr__()


class Collection:
    """Collection represents a collection (analog to a database)."""
    def __init__(self, client, name):
        self._client = client
        self.name = name

    def insert(self, doc):
        # TODO(tsileo): bulk insert
        # TODO(tsileo): file attachment
        if isinstance(doc, list):
            for d in doc:
                self._insert(d)

        r = requests.post(
            urljoin(self._client.base_url, '/api/docstore/'+self.name),
            auth=('', self._client.api_key),
            json=doc,
        )
        r.raise_for_status()
        doc_id = ID.inject(r.json())

        rdoc = doc.copy()
        del rdoc['_id']

        _DOC_CACHE[doc_id] = deepcopy(rdoc)

        return doc_id

    def update(self, doc):
        _id = doc.get('_id')
        if _id is None:
            raise Exception('missing _id')

        if _id in _DOC_CACHE:
            src = _DOC_CACHE[_id]
            p = jsonpatch.make_patch(src, doc)

            js = p.to_string()

            # special status on 412
            # (If-Match', _id.hash())
            # TODO(tsileo): a patch (JSON PATCH partial update, consistent)
        else:
            # TODO(tsileo): POST, replace the existing document (we can use the hash as an ETag too here)

    def get_by_id(self, _id):
        if isinstance(_id, ID):
            _id = _id.id()

        resp = self._client._get('/api/docstore/'+self.name+'/'+_id).json()
        doc = resp['data']
        _id = ID.inject(doc)

        # TODO(tsileo): handle pointers

        return _Document(doc)

    def _query(self, query='', script='', limit=50, cursor=''):
        # Handle raw Lua script
        if isinstance(query, LuaScript):
            script = query.script
            query = ''
        # Handle default query operators
        elif isinstance(query, (LogicalOperator, Not)):
            query = str(query)

        resp = self._client._get(
            '/api/docstore/'+self.name,
            params=dict(
                query=query,
                script=script,
                cursor=cursor,
                limit=str(limit),
            ),
        ).json()

        return resp

    def query(self, query='', script='', limit=50, cursor=''):
        return Cursor(self, query, self._query(
            query,
            script=script,
            limit=limit,
            cursor=cursor,
        ))

    def get(self, query='', script=''):
        iterator = self.query(query, script=script)
        return next(iterator)

    def __repr__(self):
        return '<blobstash.docstore.Collection name={!r}>'.format(self.name)

    def __str__(self):
        return self.__repr__()


class DocStoreClient:
    """BlobStash DocStore client."""

    def __init__(self, base_url=None, api_key=None):
        self._client = Client(base_url=base_url, api_key=api_key)

    def __getitem__(self, key):
        return self._collection(key)

    def __getattr__(self, name):
        return self._collection(name)

    def _collection(self, name):
        return Collection(self._client, name)

    def collections(self):
        """Returns all the available collections."""
        collections = []
        resp = self._client._get('/api/docstore/')
        for col in resp['collections']:
            collections.append(self._collection(col))
        return collections

    def __repr__(self):
        return '<blobstash.docstore.DocStoreClient>'

    def __str__(self):
        return self.__repr__()
