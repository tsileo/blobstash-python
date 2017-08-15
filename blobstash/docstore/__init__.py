from copy import deepcopy
from datetime import datetime
from datetime import timezone
from pathlib import Path
import json

from blobstash.base.client import Client
from blobstash.base.iterator import BasePaginationIterator
from blobstash.docstore.attachment import add_attachment
from blobstash.docstore.attachment import fadd_attachment
from blobstash.docstore.attachment import get_attachment as get_attach
from blobstash.docstore.attachment import fget_attachment
from blobstash.docstore.attachment import Attachment
from blobstash.docstore.error import DocStoreError
from blobstash.docstore.query import Q  # noqa: unused-import
from blobstash.docstore.query import LogicalOperator
from blobstash.docstore.query import Not
from blobstash.docstore.query import LuaScript
from blobstash.docstore.query import LuaShortQuery
from blobstash.docstore.query import LuaStoredQuery
from blobstash.docstore.query import LuaShortQueryComplex
from blobstash.filetree import Node

import jsonpatch

# Keep a local cache of the docs to be able to generate a JSON Patch
_DOC_CACHE = {}


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Attachment):
            return obj.pointer
        else:
            return super().default(obj)


class MissingIDError(DocStoreError):
    """Error raised when the document does not contains a `ID`."""


class NotADocumentError(DocStoreError):
    """Error raises when the given document is not a `dict` instance."""


class _Document(dict):
    """Document is a dict subclass for document returned by the API, keep track of the ETag, and the document for the
    JSON Patch generation if needed."""

    def __setitem__(self, key, val):
        if key != '_id':
            self.checkpoint()
        dict.__setitem__(self, key, val)

    def checkpoint(self):
        """Force a checkpoint for the JSON Patch generation, can be use if the dict will be used to generate an object
        (the `__setitem__` will never get triggered this way)."""
        _id = self.get('_id')
        if _id is None:
            raise MissingIDError

        if _id not in _DOC_CACHE:
            doc = self.copy()
            del doc['_id']
            _DOC_CACHE[_id] = deepcopy(doc)

    def __repr__(self):
        return dict.__repr__(self)


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
        if doc_id._hash is not None:
            del data['_hash']
        data['_id'] = doc_id
        return doc_id

    def hash(self):
        """Return the document hash/ETag."""
        return self._hash

    def id(self):
        """Return the document ID (hex-encoded)."""
        return self._id

    def created(self):
        """Return a datetime representing the document creation date (i.e. the first version)."""
        return self._parse_dt(self._created)

    def updated(self):
        """Return a datetime representing the document current version creation date."""
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
        return 'blobstash.docstore.ID(_id={!r})'.format(self._id)

    def __str__(self):
        return self._id


class DocVersionsIterator(BasePaginationIterator):

    def __init__(self, client, col_name, _id, params=None, limit=None):
        if isinstance(_id, ID):
            _id = _id.id()

        self._id = _id
        self.col_name = col_name
        super().__init__(client=client, params=params, limit=limit)

    def do_req(self, params):
        return self._client.request('GET', '/api/docstore/'+self.col_name+'/'+self._id+'/_versions', params=params)

    def parse_data(self, resp):
        raw_docs = resp['data']
        docs = []
        pointers = resp['pointers']
        for doc in raw_docs:
            ID.inject(doc)
            _fill_pointers(doc, pointers)
            docs.append(_Document(doc))

        return docs


class DocsQueryIterator(BasePaginationIterator):

    def __init__(self, client, collection, query, script='', stored_query='', stored_query_args='', as_of='', params=None, limit=None):
        self.query = query
        self.script = ''
        # TODO supprt stored query
        self.collection = collection
        self.as_of = as_of

        super().__init__(client=client, params=params, limit=limit)

    def do_req(self, params):
        return self.collection._query(
            self.query,
            script=self.script,
            cursor=params.get('cursor'),
            as_of=self.as_of,
        )

    def parse_data(self, resp):
        docs = []
        pointers = resp['pointers']
        for raw_doc in resp['data']:
            ID.inject(raw_doc)
            _fill_pointers(raw_doc, pointers)
            docs.append(_Document(raw_doc))
        return docs


def _fill_pointers(doc, pointers):
    """Replace the pointer by actual object representation."""
    for k, v in doc.items():
        if isinstance(v, str):
            if v.startswith('@filetree/ref:'):
                doc[k] = Attachment(v, Node.from_resp(pointers[v]))
        elif isinstance(v, dict):
            _fill_pointers(v, pointers)


class Collection:
    """Collection represents a collection (analog to a database)."""

    def __init__(self, client, name):
        self._client = client
        self.name = name

    def insert(self, doc):
        """Insert the given document."""
        if not isinstance(doc, dict):
            raise NotADocumentError

        if '_id' in doc and isinstance(doc['_id'], ID):
            return self.update(doc)

        # TODO(tsileo): bulk insert
        # TODO(tsileo): file attachment
        if isinstance(doc, list):
            for d in doc:
                self._insert(d)

        resp = self._client.request(
            'POST',
            '/api/docstore/'+self.name,
            json=doc,
        )
        doc_id = ID.inject(resp)

        doc['_id'] = doc_id
        rdoc = doc.copy()
        del rdoc['_id']

        _DOC_CACHE[doc_id] = deepcopy(rdoc)

        return doc_id

    def update(self, doc):
        """Update the given document/list of documents."""
        _id = doc.get('_id')
        if _id is None:
            raise MissingIDError
        del doc['_id']
        if _id in _DOC_CACHE:
            src = _DOC_CACHE[_id]
            pdoc = json.loads(json.dumps(doc, cls=JSONEncoder))
            p = jsonpatch.make_patch(src, pdoc)
            del _DOC_CACHE[_id]

            js = p.to_string()

            resp = self._client.request(
                'PATCH',
                '/api/docstore/'+self.name+'/'+_id.id(),
                headers={'If-Match': _id.hash()},
                data=js,
            )
            doc_id = ID.inject(resp)
            doc['_id'] = doc_id
            rdoc = doc.copy()
            del rdoc['_id']
            _DOC_CACHE[doc_id] = deepcopy(rdoc)
            return doc_id
            # FIXME(tsileo): catch status 412
        else:
            resp = self._client.request(
                'POST',
                '/api/docstore/'+self.name+'/'+_id.id(),
                headers={'If-Match': _id.hash()},
                json=doc,
            )
            doc_id = ID.inject(resp)
            doc['_id'] = doc_id
            rdoc = doc.copy()
            del rdoc['_id']
            _DOC_CACHE[doc_id] = deepcopy(rdoc)
            return doc_id

    def get_by_id(self, _id):
        """Fetch a document by its ID (string, a an `ID` instance)."""
        if isinstance(_id, ID):
            _id = _id.id()

        resp = self._client.request('GET', '/api/docstore/'+self.name+'/'+_id)
        doc = resp['data']
        pointers = resp['pointers']
        _id = ID.inject(doc)
        _fill_pointers(doc, pointers)

        return _Document(doc)

    def get_versions(self, _id):
        return DocVersionsIterator(self._client, self.name, _id)

        if isinstance(_id, ID):
            _id = _id.id()

        resp = self._client.request('GET', '/api/docstore/'+self.name+'/'+_id+'/_versions', params=dict(
            limit=0,
        ))
        raw_docs = resp['data']
        docs = []
        pointers = resp['pointers']
        for doc in raw_docs:
            _id = ID.inject(doc)
            _fill_pointers(doc, pointers)
            docs.append(_Document(doc))

        return docs

    def delete(self, doc_or_docs):
        """Delete the given document/list of document."""
        if isinstance(doc_or_docs, list):
            docs = [doc_or_docs]
        for doc in docs:
            if isinstance(doc, dict):
                try:
                    _id = doc['_id']
                except KeyError:
                    raise MissingIDError
            elif isinstance(_id, ID):
                _id = _id.id()
            else:
                raise NotADocumentError

            self._client.request('DELETE', '/api/docstore/'+self.name+'/'+_id)

    def _query(self, query='', script='', stored_query='', stored_query_args='', as_of='', limit=50, cursor=''):
        # XXX(tsileo): intelligent limit (i.e. limit=1000, but want to query them 100 by 100)
        # Handle raw Lua script
        if isinstance(query, LuaScript):
            script = query.script
            query = ''
        elif isinstance(query, LuaStoredQuery):
            stored_query = query.name
            stored_query_args = json.dumps(query.args)

        # Handle default query operators
        elif isinstance(query, (LogicalOperator, Not, LuaShortQueryComplex, LuaShortQuery)):
            query = str(query)
        else:
            query = str(query)

        if isinstance(as_of, datetime):
            as_of = as_of.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        resp = self._client.request(
            'GET',
            '/api/docstore/'+self.name,
            params=dict(
                query=query,
                script=script,
                stored_query_args=stored_query_args,
                stored_query=stored_query,
                cursor=cursor,
                as_of=as_of,
                limit=str(limit),
            ),
        )

        return resp

    def query(self, query='', script='', stored_query='', stored_query_args='', as_of='', limit=50, cursor=''):
        """Query the collection and return an iterable cursor."""
        return DocsQueryIterator(
            self._client,
            self,
            query,
            script=script,
            stored_query=stored_query,
            stored_query_args=stored_query_args,
            as_of=as_of,
        )

    def get(self, query='', script=''):
        """Return the first document matching the query."""
        for doc in self.query(query, script=script, limit=1):
            return doc

        return None

    def __repr__(self):
        return 'blobstash.docstore.Collection(name={!r})'.format(self.name)

    def __str__(self):
        return self.__repr__()


class DocStoreClient:
    """BlobStash DocStore client."""

    def __init__(self, base_url=None, api_key=None):
        self._client = Client(base_url=base_url, api_key=api_key, json_encoder=JSONEncoder)

    def __getitem__(self, key):
        return self._collection(key)

    def __getattr__(self, name):
        return self._collection(name)

    def _collection(self, name):
        return Collection(self._client, name)

    def collection(self, name):
        """Returns a `Collection` instance for the given name."""
        return self._collection(self._client, name)

    def collections(self):
        """Returns all the available collections."""
        collections = []
        resp = self._client.request('GET', '/api/docstore/')
        for col in resp['collections']:
            collections.append(self._collection(col))
        return collections

    def fadd_attachment(self, name=None, fileobj=None, content_type=None):
        return fadd_attachment(self._client, name, fileobj, content_type)

    def add_attachment(self, path):
        """Upload the file/dir at path, and return the key to embed the file/dir as an attachment/filetree pointer.

        >>> doc['my_super_text_file'] = client.add_attachment('/path/to/my/text_file.txt')

        """
        return add_attachment(self._client, path)

    def fget_attachment(self, attachment):
        """Returns a fileobj (that needs to be closed) with the content off the attachment."""
        return fget_attachment(self._client, attachment)

    def get_attachment(self, attachment, path):
        return get_attach(self._client, attachment, path)

    def __repr__(self):
        return 'blobstash.docstore.DocStoreClient(base_url={!r})'.format(self._client.base_url)

    def __str__(self):
        return self.__repr__()
