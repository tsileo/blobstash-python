from urllib.parse import urljoin
from datetime import datetime
from datetime import timezone

from blobstash.docstore.query import Path  # noqa: unused-import  # make it accessible
from blobstash.docstore.query import LogicalOperator
from blobstash.docstore.query import Not
from blobstash.docstore.query import LuaScript

import requests


class DocStoreID:
    def __init__(self, data):
        self._id = data.get('_id')
        self._created = data.get('_created')
        self._updated = data.get('_updated')
        self._hash = data.get('_hash')

    @classmethod
    def inject(cls, data):
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

    def __repr__(self):
        return '<DocStoreID _id={!r}>'.format(self._id)

    def __str__(self):
        return self._id


class DocStoreCursor:
    def __init__(self, collection, query, resp, limit=None):
        self._collection = collection
        self._query = query
        self._limit = limit
        self._parse_resp(resp)

    def _parse_resp(self, resp):
        self.docs = []
        for raw_doc in resp['data']:
            DocStoreID.inject(raw_doc)
            self.docs.append(raw_doc)

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
        return '<DocStoreCursor collection={!r},>'.format(self._collection.name)

    def __str__(self):
        return self.__repr__()


class DocStoreCollection:
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
        doc_id = DocStoreID.inject(r.json())
        return doc_id

    def get_by_id(self, _id):
        if isinstance(_id, DocStoreID):
            _id = _id.id()

        resp = self._client._get('/api/docstore/'+self.name+'/'+_id).json()
        doc = resp['data']
        # TODO(tsileo): handle pointers
        _id = DocStoreID.inject(doc)
        return doc, _id

    def _query(self, query='', script='', limit=50, cursor=''):
        if isinstance(query, LuaScript):
            query = ''
            script = query.script
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
        return DocStoreCursor(self, query, self._query(
            query,
            script=script,
            limit=limit,
            cursor=cursor,
        ))

    def get(self, query='', script=''):
        iterator = self.query(query, script=script)
        return next(iterator)


class DocStoreClient:
    def __init__(self, client):
        self._client = client

    def __getitem__(self, key):
        return self._collection(key)

    def __getattr__(self, name):
        return self._collection(name)

    def _collection(self, name):
        return DocStoreCollection(self._client, name)
