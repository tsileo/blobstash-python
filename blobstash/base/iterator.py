"""Base pagination iterator for traversing API respones."""


class BasePaginationIterator:
    def __init__(
        self, client, path, params=None, limit=None, per_page=None, cursor=None
    ):
        self._client = client
        self.path = path

        # Custom params that along every requests
        self.params = params or {}

        # Pagination-related data
        self.cursor = cursor
        self.per_page = per_page

        self.has_more = True
        self.items = []

        self.limit = limit
        self._returned = 0

    def parse_resp(self, resp):
        self.items = []

        try:
            self.items = self.parse_data(resp)
        except NotImplementedError:
            self.items = resp["data"]

        pagination = resp["pagination"]
        self.has_more = pagination["has_more"]
        self.cursor = pagination["cursor"]
        if self.has_more and (not self.cursor or self.cursor == "0"):
            self.has_more = False
        self.count = pagination["count"]

    def do_req(self):
        params = self.params.copy()
        params.update(limit=self.per_page, cursor=self.cursor)

        return self._client.request("GET", self.path, params=params)

    def parse_data(self, data):
        """Custom function can return a list of dict/object that will be yield during iteration."""
        raise NotImplementedError

    def __iter__(self):
        return self

    def __next__(self):
        if self.limit and self._returned == self.limit:
            raise StopIteration
        try:
            item = self.items.pop(0)
            self._returned += 1
            return item
        except IndexError:
            if not self.has_more:
                raise StopIteration
            resp = self.do_req()
            self.parse_resp(resp)
            return next(self)
