"""Query utils."""
import re


class LuaScript:
    def __init__(self, script):
        self.script = script


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


class _MetaQuery(type):
    def __getitem__(cls, key):
        if isinstance(key, int):
            return cls('[{}]'.format(key))
        return cls('.{}'.format(key))


class Q(metaclass=_MetaQuery):
    """Allow for query:

    >>> Q['persons'][0]['name'] == 'thomas'

    """

    def __init__(self, path=None):
        self._path = path or ''

    def __getitem__(self, key):
        if isinstance(key, int):
            self._path = self._path + '[{}]'.format(key)
            return self

        self._path = self._path + '.{}'.format(key)
        return self

    def path(self):
        return self._path

    def __repr__(self):
        return 'Q(path={})'.format(self._path)



class Path:
    def __init__(self, path):
        self.path = path
        self._index_regex = re.compile(r'\[\d(?!\d)\]')

    def any(self, values):
        return ' or '.join([
            'doc.{} == {}'.format(self._fix_index(self.path), self._lua_repr(value)) for value in values
        ])

    def not_any(self, values):
        return ' or '.join([
            'doc.{} ~= {}'.format(self._fix_index(self.path), self._lua_repr(value)) for value in values
        ])

    def contains(self, other):
        # FIXME(tsileo): implements in_list in BlobStash
        return 'in_list(doc.{}, {})'.format(self._fix_index(self.path), self._lua_repr(other))

    def __eq__(self, other):
        return 'doc.{} == {}'.format(self._fix_index(self.path), self._lua_repr(other))

    def __lt__(self, other):
        return 'doc.{} < {}'.format(self._fix_index(self.path), self._lua_repr(other))

    def __le__(self, other):
        return 'doc.{} <= {}'.format(self._fix_index(self.path), self._lua_repr(other))

    def __ne__(self, other):
        return 'doc.{} ~= {}'.format(self._fix_index(self.path), self._lua_repr(other))

    def __ge__(self, other):
        return 'doc.{} >= {}'.format(self._fix_index(self.path), self._lua_repr(other))

    def __gt__(self, other):
        return 'doc.{} > {}'.format(self._fix_index(self.path), self._lua_repr(other))

    def _fix_index(self, path):
        """Lua array indices start at 1, so fix this.

            >>> _fix_index("key[0].another_key")
            "key[1].another_key

        """
        return self._index_regex.sub(lambda x: '[{}]'.format(int(x.group(0)[1:-1]) + 1), path)

    def _lua_repr(self, other):

        if isinstance(other, bytes):
            return repr(other.decode('utf-8'))
        elif isinstance(other, bool):
            if other:
                return 'true'
            return 'false'
        elif isinstance(other, (str, float, int)):
            return repr(other)
        elif isinstance(other, type(None)):
            return 'nil'
        else:
            raise ValueError('unsupported data type: {}'.format(type(other)))
