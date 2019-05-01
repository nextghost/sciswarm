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

from django.utils import timezone
import datetime
import logging

logger = logging.getLogger('sciswarm')

def request_storage(request, *path):
    """Create or return dict in request.ioerp"""
    if not hasattr(request, 'ioerp'):
        request.ioerp = dict()
    tmp = request.ioerp
    for item in path:
        tmp = tmp.setdefault(item, dict())
    return tmp

def request_storage_get(request, *path, **kwargs):
    """Return object in request.ioerp if it exists"""
    default = kwargs.get('default', None)
    if not hasattr(request, 'ioerp'):
        return default
    tmp = request.ioerp
    for item in path:
        if item not in tmp:
            return default
        tmp = tmp[item]
    return tmp

# When changing session data, always set request.session.modified = True!
def session_storage(request, *path):
    """Create or return dict in session['ioerp']"""
    tmp = request.session
    for item in ['ioerp'] + list(path):
        tmp = tmp.setdefault(item, dict())
    return tmp

def session_storage_get(request, *path, **kwargs):
    """Return object in session['ioerp'] if it exists"""
    default = kwargs.get('default', None)
    tmp = request.session
    for item in ['ioerp'] + list(path):
        if item not in tmp:
            return default
        tmp = tmp[item]
    return tmp

def generate_token(bytelen):
    try:
        import secrets
        return secrets.token_urlsafe(bytelen)
    except ImportError:
        import os
        from django.utils.http import urlsafe_base64_encode
        data = os.urandom(bytelen)
        return urlsafe_base64_encode(data).decode('ascii')

def update_diff(old, new):
    oldset, newset = set(old), set(new)
    delete = list(oldset - newset)
    insert = list(newset - oldset)
    return delete, insert

def local_date():
    return timezone.localtime(timezone.now()).date()

def list_map(pair_list):
    ret = dict()
    for key, value in pair_list:
        if key in ret:
            ret[key].append(value)
        else:
            ret[key] = [value]
    return ret

def group_list(pair_list):
    ret = []
    group_map = dict()
    for key, value in pair_list:
        if key in group_map:
            group_map[key].append(value)
        else:
            tmp = [value]
            ret.append(tmp)
            group_map[key] = tmp
    return ret

def fold_and(value_list):
    if not value_list:
        return None
    if not isinstance(value_list, (list, tuple)):
        value_list = list(value_list)
    ret = value_list[0]
    for value in value_list[1:]:
        ret &= value
    return ret

def fold_or(value_list):
    if not value_list:
        return None
    if not isinstance(value_list, (list, tuple)):
        value_list = list(value_list)
    ret = value_list[0]
    for value in value_list[1:]:
        ret |= value
    return ret

def remove_duplicates(item_list, queryset=None):
    if not item_list:
        return item_list
    item_map = dict(((x.pk, x) for x in item_list))
    if queryset is not None:
        query = item_list[0].__class__.query_model.pk.belongs(list(item_map))
        del_items = queryset.filter(query).values_list('pk', flat=True)
        for key in del_items:
            del item_map[key]
    return list(item_map.values())

def make_chunks(data, chunk_size):
    pos = 0
    while pos < len(data):
        yield data[pos:pos+chunk_size]
        pos += chunk_size
