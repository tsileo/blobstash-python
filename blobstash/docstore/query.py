"""Query utils."""
import re


class LuaScript:
    def __init__(self, script):
        self.script = script


class LuaStoredQuery:
    def __init__(self, name, query_args):
        self.name = name
        self.args = query_args


class LogicalOperator:
    def __init__(self, *args):
        self.clauses = args

    def __str__(self):
        return ' {} '.format(self.OPERATOR).join([str(clause) for clause in self.clauses])


class Or(LogicalOperator):
    OPERATOR = 'or'


class And(LogicalOperator):
    OPERATOR = 'and'


class Not:
    def __init__(self, clause):
        self.clause = clause

    def __str__(self):
        return 'not ({})'.format(str(self.clause))


def _lua_repr(value):
    if isinstance(value, bytes):
        return repr(value.decode('utf-8'))
    elif isinstance(value, bool):
        if value:
            return 'true'
        return 'false'
    elif isinstance(value, str):
        return repr(value)
    elif isinstance(value, (float, int)):
        return value
    elif isinstance(value, type(None)):
        return 'nil'
    # XXX(tsileo): should `dict`/`list` be supported?
    else:
        raise ValueError('unsupported data type: {}'.format(type(value)))


class LuaShortQuery:

    def __init__(self, key, value, operator):
        self.key = key
        self.value = value
        self.operator = operator

    def query(self):
        return "match(doc, '{}', '{}', {})".format(self.key, self.operator, _lua_repr(self.value))

    def __str__(self):
        return self.query()


class LuaShortQueryComplex:
    def __init__(self, query):
        self.query = query

    def __str__(self):
        return self.query


class _MetaQuery(type):
    def __getitem__(cls, key):
        if isinstance(key, int):
            return cls('[{}]'.format(key+1))
        return cls('.{}'.format(key))


class Q(metaclass=_MetaQuery):
    """Allow for query:

    >>> Q['persons_count'] > 5
    >>> Q['persons'][0]['name'] == 'thomas'
    >>> Q['l'].contains(10)
    >>> Q['persons'].contains(Q['name'] == 'thomas')

    """

    def __init__(self, path=None):
        self._path = path or ''

    def __getitem__(self, key):
        if isinstance(key, int):
            self._path = self._path + '[{}]'.format(key+1)
            return self

        self._path = self._path + '.{}'.format(key)
        return self

    def path(self):
        return self._path[1:]

    def __repr__(self):
        return 'Q(path={})'.format(self._path)

    def any(self, values):
        return LuaShortQueryComplex(' or '.join([
            "get_path(doc, '{}') == {}".format(self.path(), _lua_repr(value)) for value in values
        ]))

    def not_any(self, values):
        return LuaShortQueryComplex(' or '.join([
            "get_path(doc, '{}') ~= {}".format(self.path(), _lua_repr(value)) for value in values
        ]))

    def contains(self, q):
        if isinstance(q, LuaShortQuery):
            if q.operator != 'EQ':
                raise ValueError('contains only support pure equality query')
            return LuaShortQueryComplex("in_list(doc, '{}', {}, '{}')".format(
                self.path(),
                _lua_repr(q.value),
                q.key,
            ))
        elif isinstance(q, LuaShortQueryComplex):
            raise ValuError('query too complex to use in contains')

        return LuaShortQueryComplex("in_list(doc, '{}', {})".format(
            self.path(),
            _lua_repr(q),
        ))

    def __eq__(self, other):
        return LuaShortQuery(self.path(), _lua_repr(other), 'EQ')

    def __ne__(self, other):
        return LuaShortQuery(self.path(), _lua_repr(other), 'NE')

    def __lt__(self, other):
        return LuaShortQuery(self.path(), _lua_repr(other), 'LT')

    def __le__(self, other):
        return LuaShortQuery(self.path(), _lua_repr(other), 'LE')

    def __ge__(self, other):
        return LuaShortQuery(self.path(), _lua_repr(other), 'GE')

    def __gt__(self, other):
        return LuaShortQuery(self.path(), _lua_repr(other), 'GT')
