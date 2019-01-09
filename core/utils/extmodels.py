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

from django.db import models
from django.db.models.fields.related import RelatedField
from django.db.models.fields.reverse_related import ForeignObjectRel
from collections import namedtuple
import types

class QueryExpression(object):
    """Base class for pythonic SQL expressions"""

    def __init__(self, tokens):
        self._tokens = tokens

    def _query(self, **kwarg):
        if len(kwarg) != 1:
            raise RuntimeError('Exactly one keyword argument required')
        op, value = kwarg.popitem()
        return models.Q(**{'__'.join(self._tokens + [op]): value})

    def isnull(self):
        return self._query(isnull=True)

    def notnull(self):
        return self._query(isnull=False)

    def belongs(self, other):
        return self._query(**{'in':other})

    def f(self):
        return models.F('__'.join(self._tokens))

    def __eq__(self, other):
        return self._query(exact=other)

    def __ne__(self, other):
        return ~self._query(exact=other)

    def resolve_expression(self, *args, **kwargs):
        return self.f().resolve_expression(*args, **kwargs)

class OrderedQueryExpression(QueryExpression):
    def between(self, start, end):
        return self._query(**{'range':(start, end)})

    def __lt__(self, other):
        return self._query(lt=other)

    def __le__(self, other):
        return self._query(lte=other)

    def __gt__(self, other):
        return self._query(gt=other)

    def __ge__(self, other):
        return self._query(gte=other)

class StringQueryMixin(object):
    def iexact(self, other):
        return self._query(iexact=other)

    def contains(self, other):
        return self._query(contains=other)

    def icontains(self, other):
        return self._query(icontains=other)

    def startswith(self, other):
        return self._query(startswith=other)

    def istartswith(self, other):
        return self._query(istartswith=other)

    def endswith(self, other):
        return self._query(endswith=other)

    def iendswith(self, other):
        return self._query(iendswith=other)

    def search(self, other):
        return self._query(search=other)

    def regex(self, other):
        return self._query(regex=other)

    def iregex(self, other):
        return self._query(iregex=other)

class NumericQueryMixin(object):
    def __add__(self, other):
        return self.f() + other

    def __sub__(self, other):
        return self.f() - other

    def __mul__(self, other):
        return self.f() * other

    def __truediv__(self, other):
        return self.f() / other

    def __div__(self, other):
        return self.__truediv__(other)

    def __mod__(self, other):
        return self.f() % other

    def __pow__(self, other):
        return self.f() ** other

    def __radd__(self, other):
        return other + self.f()

    def __rsub__(self, other):
        return other - self.f()

    def __rmul__(self, other):
        return other * self.f()

    def __rtruediv__(self, other):
        return other / self.f()

    def __rdiv__(self, other):
        return self.__rtruediv__(other)

    def __rmod__(self, other):
        return other % self.f()

    def __rpow__(self, other):
        return other ** self.f()

class ReferenceQueryMixin(object):
    def __getattr__(self, name):
        return getattr(self._model.query_model, name)._expr(self._tokens)

class StringQueryExpression(StringQueryMixin, OrderedQueryExpression):
    pass

class NumericQueryExpression(NumericQueryMixin, OrderedQueryExpression):
    pass

class ReferenceQueryExpression(ReferenceQueryMixin, QueryExpression):
    def __init__(self, tokens, model):
        super(ReferenceQueryExpression, self).__init__(tokens)
        self._model = model

class QueryField(OrderedQueryExpression):
    """Base class for expression-based fields"""

    def __init__(self, field):
        super(QueryField, self).__init__([field.name])
        self._field = field

    def _expr(self, prefix):
        return OrderedQueryExpression(prefix + [self._field.name])

class NumericQueryField(NumericQueryMixin, QueryField):
    """Class for expression-based numeric fields"""

    def _expr(self, prefix):
        return NumericQueryExpression(prefix + [self._field.name])

class StringQueryField(StringQueryMixin, QueryField):
    """Class for expression-based string fields"""

    def _expr(self, prefix):
        return StringQueryExpression(prefix + [self._field.name])

class QueryReference(ReferenceQueryMixin, QueryExpression):
    def __init__(self, name, model):
        super(QueryReference, self).__init__([name])
        self._name = name
        self._model = model

    def _expr(self, prefix):
        return ReferenceQueryExpression(prefix + [self._name], self._model)

def create_query_model(model_list):
    """Call this from AppConfig.ready() to install query model"""
    numeric_types = (models.AutoField, models.DecimalField, models.FloatField,
        models.IntegerField)
    string_types = (models.CharField, models.FilePathField, models.TextField)

    for cls in model_list:
        if not issubclass(cls, models.Model):
            raise TypeError("'{0}' is not a model".format(str(cls)))
        if hasattr(cls, 'query_model'):
            continue
        query_fields = dict()
        for field in cls._meta.get_fields():
            if (not field.concrete) and not isinstance(field,ForeignObjectRel):
                continue
            if isinstance(field, numeric_types):
                new_field = NumericQueryField(field)
            elif isinstance(field, string_types):
                new_field = StringQueryField(field)
            elif isinstance(field, RelatedField):
                new_field = QueryReference(field.name,field.remote_field.model)
            elif isinstance(field, ForeignObjectRel):
                new_field = QueryReference(field.name, field.field.model)
            else:
                new_field = QueryField(field)
            query_fields[field.name] = new_field
            if (field.concrete and field.primary_key and
                'pk' not in query_fields):
                query_fields['pk'] = new_field
        ret_type = namedtuple(cls.__name__ + 'QueryModel', list(query_fields))
        cls.add_to_class('query_model', ret_type(**query_fields))
