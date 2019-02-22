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

@models.Field.register_lookup
class TSPlain(models.Lookup):
    lookup_name = 'tsplain'
    prepare_rhs = False

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        if isinstance(self.rhs, (list, tuple)):
            conf, query = self.rhs
        else:
            conf = 'simple'
            query = self.rhs
        params = [conf] + lhs_params + [conf, query]
        sql = 'to_tsvector(%%s, %s) @@ plainto_tsquery(%%s, %%s)' % lhs
        return sql, params

@models.Field.register_lookup
class TSPhrase(models.Lookup):
    lookup_name = 'tsphrase'
    prepare_rhs = False

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        if isinstance(self.rhs, (list, tuple)):
            conf, query = self.rhs
        else:
            conf = 'simple'
            query = self.rhs
        params = [conf] + lhs_params + [conf, query]
        sql = 'to_tsvector(%%s, %s) @@ phraseto_tsquery(%%s, %%s)' % lhs
        return sql, params

@models.Field.register_lookup
class TSQuery(models.Lookup):
    lookup_name = 'tsquery'
    prepare_rhs = False

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        if isinstance(self.rhs, (list, tuple)):
            conf, query = self.rhs
        else:
            conf = 'simple'
            query = self.rhs
        params = [conf] + lhs_params + [conf, query]
        sql = 'to_tsvector(%%s, %s) @@ to_tsquery(%%s, %%s)' % lhs
        return sql, params
