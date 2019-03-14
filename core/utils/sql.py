# This file is part of Sciswarm, a scientific social network
# Copyright (C) 2018-2019 Martin Doucha
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from django.db.models.expressions import OrderBy
from django.db.models.sql import compiler
from django.db import models, DEFAULT_DB_ALIAS, connections
from django.utils import timezone
from collections import OrderedDict

class SQLSyntaxError(RuntimeError):
    pass

# Expression operators

class UnaryPrefixOp(object):
    def __init__(self, op):
        self._op = op

    def __call__(self, value):
        return '({op} {val})'.format(op=self._op, val=value)

class UnaryPostfixOp(object):
    def __init__(self, op):
        self._op = op

    def __call__(self, value):
        return '({val} {op})'.format(op=self._op, val=value)

class BinaryOp(object):
    def __init__(self, op):
        self._op = op

    def __call__(self, lhs, rhs):
        return '({lhs} {op} {rhs})'.format(op=self._op, lhs=lhs, rhs=rhs)

class FunctionOp(object):
    def __init__(self, name, min_args=1, max_args=1):
        self._name = name
        self._min_args = min_args
        self._max_args = max_args

    def __call__(self, *args):
        if self._min_args is not None and len(args) < self._min_args:
            msg = '{name}(): Too few arguments, {cnt} required.'
            raise SQLSyntaxError(msg.format(name=self._name,cnt=self._min_args))
        elif self._max_args is not None and len(args) > self._max_args:
            msg = '{name}(): Too many arguments, at most {cnt} supported.'
            raise SQLSyntaxError(msg.format(name=self._name,cnt=self._max_args))
        return '{func}({args})'.format(func=self._name, args=','.join(args))

class CountOp(object):
    def __init__(self, distinct=False):
        if distinct:
            self.template = 'COUNT(DISTINCT {arg})'
        else:
            self.template = 'COUNT({arg})'

    def __call__(self, arg):
        return self.template.format(arg=arg)

# Expressions

def make_expr(value):
    if isinstance(value, Expression):
        return value
    return ConstExpression(value)

def same_expr_type_class(expr):
    if isinstance(expr, NumericMixin):
        return NumericExpression
    elif isinstance(expr, StringMixin):
        return StringExpression
    elif isinstance(expr, BooleanMixin):
        return BooleanExpression
    else:
        return Expression

def same_expr_type_field(expr, table, name):
    if isinstance(expr, Field):
        return expr.__class__(table, name, name)
    if isinstance(expr, NumericMixin):
        return NumericField(table, name, name)
    elif isinstance(expr, StringMixin):
        return StringField(table, name, name)
    elif isinstance(expr, BooleanMixin):
        return BooleanField(table, name, name)
    else:
        return Field(table, name, name)

class Expression(object):
    NEG = UnaryPrefixOp('-')
    ADD = BinaryOp('+')
    SUB = BinaryOp('-')
    MUL = BinaryOp('*')
    DIV = BinaryOp('/')
    MOD = BinaryOp('%')

    ISNULL = UnaryPostfixOp('IS NULL')
    NOTNULL = UnaryPostfixOp('IS NOT NULL')
    EQ = BinaryOp('=')
    NEQ = BinaryOp('<>')
    LT = BinaryOp('<')
    LTE = BinaryOp('<=')
    GT = BinaryOp('>')
    GTE = BinaryOp('>=')

    NOT = UnaryPrefixOp('NOT')
    AND = BinaryOp('AND')
    OR = BinaryOp('OR')

    def __init__(self, op, *children):
        self._op = op
        self._children = children

    def as_sql(self, compiler, connection):
        children = []
        ret_params = []
        for child in self._children:
            sql, params = compiler.compile(child)
            children.append(sql)
            ret_params.extend(params)
        return self._op(*children), ret_params

    def resolve_expression(self, query=None, allow_joins=True, reuse=None,
        summarize=False, for_save=False):
        return self

    def get_db_converters(self, connection):
        return []

    def isnull(self):
        return BooleanExpression(Expression.ISNULL, self)

    def notnull(self):
        return BooleanExpression(Expression.NOTNULL, self)

    def belongs(self, other):
        return BelongsExpression(self, other)

    def __eq__(self, other):
        if other is None:
            return self.isnull()
        return BooleanExpression(Expression.EQ, self, make_expr(other))

    def __ne__(self, other):
        if other is None:
            return self.notnull()
        return BooleanExpression(Expression.NEQ, self, make_expr(other))

class OrderedMixin(object):
    def __lt__(self, other):
        return BooleanExpression(Expression.LT, self, make_expr(other))

    def __le__(self, other):
        return BooleanExpression(Expression.LTE, self, make_expr(other))

    def __gt__(self, other):
        return BooleanExpression(Expression.GT, self, make_expr(other))

    def __ge__(self, other):
        return BooleanExpression(Expression.GTE, self, make_expr(other))

    def asc(self):
        return OrderBy(self, False)

    def desc(self):
        return OrderBy(self, True)

class BooleanMixin(OrderedMixin):
    def __invert__(self):
        return BooleanExpression(Expression.NOT, self)

    def __and__(self, other):
        return BooleanExpression(Expression.AND, self, make_expr(other))

    def __or__(self, other):
        return BooleanExpression(Expression.OR, self, make_expr(other))

    def __rand__(self, other):
        return BooleanExpression(Expression.AND, make_expr(other), self)

    def __ror__(self, other):
        return BooleanExpression(Expression.OR, make_expr(other), self)

class NumericMixin(OrderedMixin):
    def __neg__(self):
        return NumericExpression(Expression.NEG, self)

    def __add__(self, other):
        return NumericExpression(Expression.ADD, self, make_expr(other))

    def __sub__(self, other):
        return NumericExpression(Expression.SUB, self, make_expr(other))

    def __mul__(self, other):
        return NumericExpression(Expression.MUL, self, make_expr(other))

    def __truediv__(self, other):
        return NumericExpression(Expression.DIV, self, make_expr(other))

    def __div__(self, other):
        return NumericExpression(Expression.DIV, self, make_expr(other))

    def __mod__(self, other):
        return NumericExpression(Expression.MOD, self, make_expr(other))

    def __radd__(self, other):
        return NumericExpression(Expression.ADD, make_expr(other), self)

    def __rsub__(self, other):
        return NumericExpression(Expression.SUB, make_expr(other), self)

    def __rmul__(self, other):
        return NumericExpression(Expression.MUL, make_expr(other), self)

    def __rtruediv__(self, other):
        return NumericExpression(Expression.DIV, make_expr(other), self)

    def __rdiv__(self, other):
        return NumericExpression(Expression.DIV, make_expr(other), self)

    def __rmod__(self, other):
        return NumericExpression(Expression.MOD, make_expr(other), self)

class StringMixin(OrderedMixin):
    def like(self, pattern):
        return LikeExpression(self, pattern, False)

    def ilike(self, pattern):
        return LikeExpression(self, pattern, True)

    def contains(self, value):
        return ContainsExpression(self, value, False)

    def icontains(self, value):
        return ContainsExpression(self, value, True)

    def startswith(self, value):
        return StartsWithExpression(self, value, False)

    def istartswith(self, value):
        return StartsWithExpression(self, value, True)

    def tsplain(self, query, conf='simple'):
        return TSExpression('plainto_tsquery', self, query, conf)

    def tsphrase(self, query, conf='simple'):
        return TSExpression('phraseto_tsquery', self, query, conf)

    def tsquery(self, query, conf='simple'):
        return TSExpression('to_tsquery', self, query, conf)

class ConstExpression(Expression):
    def __init__(self, value):
        self._value = value

    def as_sql(self, compiler, connection):
        return '%s', [self._value]

class OrderedExpression(OrderedMixin, Expression):
    pass

class BooleanExpression(BooleanMixin, Expression):
    pass

class NumericExpression(NumericMixin, Expression):
    pass

class StringExpression(StringMixin, Expression):
    pass

class SubqueryExpression(Expression):
    def __init__(self, query):
        self._query = query

    def as_sql(self, compiler, connection):
        comp2 = self._query.get_compiler(connection=connection)
        return comp2.as_sql()

class BelongsExpression(BooleanExpression):
    def __init__(self, lhs, rhs):
        self._lhs = lhs
        self._rhs = rhs

    def as_sql(self, compiler, connection):
        template = '({lhs} IN ({rhs}))'
        lhs, ret_params = compiler.compile(self._lhs)
        if isinstance(self._rhs, (list, tuple)):
            if not self._rhs:
                return compiler.compile(ConstExpression(False))
            tmp = [compiler.compile(ConstExpression(x)) for x in self._rhs]
            rhs = ','.join((x[0] for x in tmp))
            ret_params.extend((y for x in tmp for y in x[1]))
        elif isinstance(self._rhs, SelectQuery):
            query = self._rhs
            if len(query.fields) + len(query.falias) > 1:
                raise ValueError('"IN" subquery must return only 1 column')
            comp2 = self._rhs.get_compiler(connection=connection)
            rhs, params = comp2.as_sql()
            ret_params.extend(params)
        else:
            raise ValueError('Invalid argument for "IN" expression')
        return template.format(lhs=lhs, rhs=rhs), ret_params

class LikeExpression(BooleanExpression):
    def __init__(self, lhs, pattern, ignore_case=False):
        self._lhs = lhs
        self._pattern = pattern
        self._ignore_case = ignore_case

    def process_pattern(self, compiler, connection):
        return self._pattern

    def as_sql(self, compiler, connection):
        if self._ignore_case:
            template = '(UPPER({lhs}) LIKE UPPER(%s))'
        else:
            template = '({lhs} LIKE %s)'
        lhs, ret_params = compiler.compile(self._lhs)
        ret_params.append(self.process_pattern(compiler, connection))
        return template.format(lhs=lhs), ret_params

class ContainsExpression(LikeExpression):
    def process_pattern(self, compiler, connection):
        pattern = connection.ops.prep_for_like_query(self._pattern)
        return '%{0}%'.format(pattern)

class StartsWithExpression(LikeExpression):
    def process_pattern(self, compiler, connection):
        pattern = connection.ops.prep_for_like_query(self._pattern)
        return '{0}%'.format(pattern)

class DateTimeExtractExpression(NumericExpression):
    def __init__(self, component, field):
        self._component = component
        self._field = field

    def as_sql(self, compiler, connection):
        sql, params = compiler.compile(self._field)
        if isinstance(self._field, DateTimeField):
            tzname = timezone.get_current_timezone_name()
            sql, params2 = connection.ops.datetime_extract_sql(self._component,
                sql, tzname)
            params.extend(params2)
        elif isinstance(self._field, DateField):
            sql = connection.ops.date_extract_sql(self._component, sql)
        elif isinstance(self._field, TimeField):
            sql = connection.ops.time_extract_sql(self._component, sql)
        else:
            msg = 'Cannot extract date/time components form %s object'
            raise ValueError(msg % self._field.__class__.__name__)
        return sql, params

class TSExpression(BooleanExpression):
    def __init__(self, parser, lhs, query, conf='simple'):
        self._parser = parser
        self._lhs = lhs
        self._query = query
        self._config = conf

    def as_sql(self, compiler, connection):
        sql, lhs_params = compiler.compile(self._lhs)
        tpl = 'to_tsvector(%s, {lhs}) @@ {parser}(%s, %s)'
        sql = tpl.format(lhs=sql, parser=self._parser)
        params = [self._config] + lhs_params + [self._config, self._query]
        return sql, params

class Field(Expression):
    def __init__(self, table, attname, column):
        self._table = table
        self._name = attname
        self._column = column

    def as_sql(self, compiler, connection):
        name = compiler.connection.ops.quote_name(self._column)
        alias = compiler.query.table_aliases[self._table]
        return '{table}.{name}'.format(table=alias, name=name), []

class BooleanField(BooleanMixin, Field):
    pass

class NumericField(NumericMixin, Field):
    pass

class StringField(StringMixin, Field):
    pass

class DateField(OrderedMixin, Field):
    pass

class TimeField(OrderedMixin, Field):
    pass

class DateTimeField(OrderedMixin, Field):
    pass

def coalesce(*exprs):
    children = [make_expr(x) for x in exprs]
    cls = same_expr_type_class(children[0])
    return cls(FunctionOp('COALESCE', max_args=None), *children)

def min(expr):
    expr = make_expr(expr)
    return same_expr_type_class(expr)(FunctionOp('MIN'), expr)

def max(expr):
    expr = make_expr(expr)
    return same_expr_type_class(expr)(FunctionOp('MAX'), expr)

def sum(expr):
    expr = make_expr(expr)
    return same_expr_type_class(expr)(FunctionOp('SUM'), expr)

def clean_sum(expr):
    return coalesce(sum(expr), 0)

def count(expr, distinct=False):
    return NumericExpression(CountOp(distinct), make_expr(expr))

def avg(expr):
    return NumericExpression(FunctionOp('AVG'), expr)

def stddev_pop(expr):
    return NumericExpression(FunctionOp('STDDEV_POP'), expr)

def stddev_samp(expr):
    return NumericExpression(FunctionOp('STDDEV_SAMP'), expr)

def all(query):
    return Expression(FunctionOp('ALL'), SubqueryExpression(query))

# Note: PostgreSQL ignores NULL values in GREATEST() and LEAST()
# MySQL returns NULL if any argument is NULL.
def greatest(*exprs):
    children = (make_expr(x) for x in exprs)
    return OrderedExpression(FunctionOp('GREATEST', max_args=None), *children)

def least(*exprs):
    children = (make_expr(x) for x in exprs)
    return OrderedExpression(FunctionOp('LEAST', max_args=None), *children)

def year(field):
    return DateTimeExtractExpression('year' ,field)

def month(field):
    return DateTimeExtractExpression('month', field)

def day(field):
    return DateTimeExtractExpression('day', field)

def hour(field):
    return DateTimeExtractExpression('hour', field)

def minute(field):
    return DateTimeExtractExpression('minute', field)

def second(field):
    return DateTimeExtractExpression('second', field)

def upper(expr):
    return StringExpression(FunctionOp('UPPER'), expr)

def lower(expr):
    return StringExpression(FunctionOp('LOWER'), expr)

# Tables and Joins

class Joinable(object):
    def inner_join(self, other, on):
        return Join('INNER', self, other, on)

    def left_join(self, other, on):
        return Join('LEFT', self, other, on)

    def right_join(self, other, on):
        return Join('RIGHT', self, other, on)

    def full_join(self, other, on):
        return Join('FULL', self, other, on)

    def select(self, *fields, alias=dict(), where=None, group_by=[],
        having=None, order_by=[], limit=None, distinct=False, lock=False):

        return SelectQuery(fields, alias, self, where, group_by, having,
            order_by, limit, distinct, lock)

class Join(Joinable):
    def __init__(self, join_type, tbl1, tbl2, on):
        self._join_type = join_type
        self._tbl1 = tbl1
        self._tbl2 = tbl2
        self._on = on

    def as_sql(self, compiler, connection):
        t1, params = compiler.compile(self._tbl1)
        t2, params2 = compiler.compile(self._tbl2)
        on, params_on = compiler.compile(self._on)
        params.extend(params2)
        params.extend(params_on)
        tpl = '({t1} {jtype} JOIN {t2} ON {on})'
        return tpl.format(t1=t1, t2=t2, jtype=self._join_type, on=on), params

# Table must remain hashable, do *NOT* implement __eq__()
class Table(Joinable):
    def __init__(self, model):
        self._model = model
        self.fields = []
        self._fieldmap = dict()
        typemap = [
            (NumericField, (models.AutoField, models.DecimalField,
                models.FloatField, models.IntegerField)),
            (StringField, (models.CharField, models.TextField)),
            (BooleanField, (models.BooleanField, models.NullBooleanField)),
            (DateField, (models.DateField,)),
            (TimeField, (models.TimeField,)),
            (DateTimeField, (models.DateTimeField,)),
        ]

        for field in model._meta.get_fields():
            if not field.concrete:
                continue
            for fcls, types in typemap:
                if isinstance(field, types):
                    new_field = fcls(self, field.attname, field.column)
                    break
            else:
                new_field = Field(self, field.attname, field.column)
            self.fields.append(field.attname)
            self._fieldmap[field.attname] = new_field
            if field.primary_key and 'pk' not in self._fieldmap:
                self._fieldmap['pk'] = new_field

    def __contains__(self, name):
        return name in self._fieldmap

    def __getitem__(self, name):
        return self._fieldmap[name]

    def __getattr__(self, name):
        if not name in self:
            msg = "'{0}' object has no attribute '{1}'"
            raise AttributeError(msg.format(self.__class__.__name__, name))
        return self[name]

    def as_sql(self, compiler, connection):
        name = compiler.connection.ops.quote_name(self._model._meta.db_table)
        alias = compiler.query.table_aliases[self]
        return '{table} AS {alias}'.format(table=name, alias=alias), []

    def mapping(self, **annotations):
        fields = self._fieldmap.copy()
        fields.pop('pk', None)
        return ModelMapping(self._model, alias=fields, annotations=annotations)

# Query, compiler and result classes

# SelectQuery must remain hashable, do *NOT* implement __eq__()
class SelectQuery(Joinable):
    def __init__(self, fields, alias, from_, where, group_by, having, order_by,
        limit, distinct, lock):
        if len(fields) + len(alias) < 1:
            raise SQLSyntaxError('No fields selected.')
        self.fields = [make_expr(x) for x in fields]
        self.falias = dict(((k, make_expr(v)) for k, v in alias.items()))
        self.from_ = from_
        self.where = where
        self.group_by = [make_expr(x) for x in group_by]
        self.having = having
        self.order_by = order_by
        self.low_mark = None
        self.high_mark = None
        self.distinct = distinct
        self.select_for_update = lock
        self.table_aliases = dict()
        self._fieldmap = dict()
        # Compatibility attributes
        self.alias_refcount = {}
        self.alias_map = OrderedDict()
        self.tables = []
        self.default_cols = False
        self.subquery = False
        self.select_for_update_nowait = False
        self.combinator = None
        self.combinator_all = False
        self.combined_queries = ()

        if limit is not None:
            self.low_mark = limit[0]
            self.high_mark = limit[0] + limit[1]

        self._generate_aliases(self.from_)

        for expr in self.fields:
            if isinstance(expr, Field):
                new_field = same_expr_type_field(expr, self, expr._name)
                self._fieldmap[expr._name] = new_field
        for alias, expr in self.falias.items():
            self._fieldmap[alias] = same_expr_type_field(expr, self, alias)

    def _generate_aliases(self, node):
        if isinstance(node, (Table, SelectQuery)):
            if node in self.table_aliases:
                msg = 'Same copy of table joined multiple times in query'
                raise SQLSyntaxError(msg)
            alias = 't{}'.format(len(self.table_aliases))
            self.table_aliases[node] = alias
        elif isinstance(node, Join):
            self._generate_aliases(node._tbl1)
            self._generate_aliases(node._tbl2)
        else:
            msg = 'Invalid object in query FROM clause: {}'
            raise SQLSyntaxError(msg.format(repr(node)))

    def get_compiler(self, using=None, connection=None):
        if using is None and connection is None:
            raise ValueError("Need either using or connection")
        if using:
            connection = connections[using]
        return SelectCompiler(self, connection, using)

    def __contains__(self, name):
        return name in self._fieldmap

    def __getitem__(self, name):
        return self._fieldmap[name]

    def __getattr__(self, name):
        if name not in self:
            msg = "'{0}' object has no attribute '{1}'"
            raise AttributeError(msg.format(self.__class__.__name__, name))
        return self[name]

    def __str__(self):
        sql, params = self.sql_with_params()
        return sql % params

    def sql_with_params(self):
        return self.get_compiler(DEFAULT_DB_ALIAS).as_sql()

    def as_sql(self, compiler, connection):
        comp2 = self.get_compiler(connection=connection)
        sql, params = comp2.as_sql()
        alias = compiler.query.table_aliases[self]
        return '({sql}) AS {alias}'.format(sql=sql, alias=alias), list(params)

    def queryset(self, model, translations=None):
        sql, params = self.get_compiler(model.objects.db).as_sql()
        return model.objects.raw(sql, params, translations)

    def execute(self, using=None, connection=None):
        if using is None and connection is None:
            using = DEFAULT_DB_ALIAS
        compiler = self.get_compiler(using=using)
        return SQLResult(compiler, compiler.execute_sql())

    def __iter__(self):
        return iter(self.execute())

    def model_result(self, mapping, using=None, connection=None):
        if using is None and connection is None:
            using = DEFAULT_DB_ALIAS
        compiler = self.get_compiler(using=using)
        return ModelResult(mapping, compiler, compiler.execute_sql())

    # Django QuerySet/SQLCompiler compatibility methods

    def clone(self):
        # FIXME: clone expressions and FROM clause
        ret = SelectQuery(self.fields[:], self.falias.copy(), self.from_,
            self.where, self.group_by[:], self.having, self.order_by[:],
            None, self.distinct, self.select_for_update)
        ret.low_mark = self.low_mark
        ret.high_mark = self.high_mark
        return ret

    def clear_ordering(self, force_empty):
        self.order_by = []

    def _prepare(self, field):
        if len(self.fields) + len(self.falias) != 1:
            raise SQLSyntaxError('Nested query must select exactly 1 column')
        return self

    def is_compatible_query_object_type(self, opts, field):
        return True

    def get_initial_alias(self):
        pass

    def reset_refcounts(self, data):
        pass

class SelectCompiler(compiler.SQLCompiler):
    def pre_sql_setup(self):
        self.setup_query()
        order_by = self.get_order_by()
        self.where, self.having = self.query.where, self.query.having
        self.has_extra_select = False
        group_by = self.get_group_by(self.select, order_by)
        return [], order_by, group_by

    def get_group_by(self, select, order_by):
        if self.query.group_by is None:
            return []
        ret = []
        for expr in self.query.group_by:
            sql, params = self.compile(expr)
            ret.append((sql, params))
        return ret

    def get_select(self):
        ret = []
        annotations = dict()
        for expr in self.query.fields:
            ret.append((expr, self.compile(expr), None))
        for alias, expr in self.query.falias.items():
            annotations[alias] = len(ret)
            ret.append((expr, self.compile(expr), alias))
        return ret, None, annotations
        
    def get_order_by(self):
        if self.query.order_by is None:
            return []
        ret = []
        for expr in self.query.order_by:
            sql, params = self.compile(expr)
            ret.append((expr, (sql, params, False)))
        return ret

    def get_distinct(self):
        if not isinstance(self.query.distinct, (list, tuple)):
            return []
        ret = []
        for expr in self.query.distinct:
            sql, params = self.compile(expr)
            if params:
                raise SQLSyntaxError('"DISTINCT ON" with params not supported')
            ret.append(sql)
        return ret

    def get_from_clause(self):
        sql, params = self.compile(self.query.from_)
        return [sql], params

    def has_results(self):
        raise NotImplementedError('FIXME')

    def as_subquery_condition(self, alias, columns, compiler):
        raise NotImplementedError('FIXME')

class SQLRow(object):
    def __init__(self, parent, data):
        self.db = parent.db
        self.exprmap = parent.exprmap
        self.namemap = parent.namemap
        self.data = data

    def __contains__(self, idx):
        if isinstance(idx, Expression):
            return id(idx) in self.exprmap
        elif isinstance(idx, str):
            return idx in self.namemap
        else:
            return idx < len(self.data)

    def __getitem__(self, idx):
        if isinstance(idx, Expression):
            return self.data[self.exprmap[id(idx)]]
        elif isinstance(idx, str):
            return self.data[self.namemap[idx]]
        else:
            return self.data[idx]

    def __str__(self):
        return str(self.data)

    def __iter__(self):
        return iter(self.data)

class SQLResult(object):
    def __init__(self, compiler, result):
        self.data = result
        self.db = compiler.using
        exprmap = dict()
        namemap = dict()
        for idx, (expr, _, alias) in enumerate(compiler.select):
            exprmap[id(expr)] = idx
            if isinstance(expr, Field) or alias is not None:
                namemap[alias or expr._name] = idx
        self.exprmap = exprmap
        self.namemap = namemap

    def __iter__(self):
        for rset in self.data:
            for row in rset:
                yield SQLRow(self, row)

    def first(self):
        for rset in self.data:
            for row in rset:
                return SQLRow(self, row)
        return None

class ModelMapping(object):
    def __init__(self, model, *fields, alias=dict(), annotations=dict()):
        self.model = model
        self.fields = dict((x._name, x) for x in fields)
        self.annotations = dict()
        for key, field in alias.items():
            if isinstance(field, Table):
                field = field.mapping()
            self.fields[key] = field
        for key, field in annotations.items():
            if isinstance(field, Table):
                field = field.mapping()
            self.annotations[key] = field

    def parse(self, row):
        names = []
        values = []
        for modelfield in self.model._meta.concrete_fields:
            field = self.fields.get(modelfield.attname)
            if field is not None and field in row:
                values.append(row[field])
                names.append(modelfield.attname)
        ret = self.model.from_db(row.db, names, values)
        # FIXME: Properly populate both sides of foreign key reference
        for name, field in self.annotations.items():
            if isinstance(field, ModelMapping):
                value = field.parse(row)
            else:
                value = row[field]
            setattr(ret, name, value)
        return ret

class ModelResult(SQLResult):
    def __init__(self, mapping, compiler, result):
        super(ModelResult, self).__init__(compiler, result)
        self.mapping = mapping

    def __iter__(self):
        for rset in self.data:
            for row in rset:
                yield self.mapping.parse(SQLRow(self, row))
