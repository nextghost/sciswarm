from django.utils import timezone
import datetime
import logging

logger = logging.getLogger('ioerp')

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

def czech_holidays(year):
    dates = [(1, 1), (1, 5), (8, 5), (5, 7), (6, 7), (28, 9), (28, 10),
        (17, 11), (24, 12), (25, 12), (26, 12)]

    # Easter date
    gn = (year % 19) + 1
    century = (year // 100) + 1
    x = (3 * century) // 4 - 12
    z = (8 * century + 5) // 25 - 5
    sunday = (5 * year) // 4 - x - 10
    epact = (11 * gn + 20 + z - x) % 30
    if epact == 24 or (epact == 25 and gn > 11):
        epact += 1
    full_moon = 44 - epact
    if full_moon < 21:
        full_moon += 30
    s2 = full_moon + 7 - (sunday + full_moon) % 7

    tmp = [(tmp - 31, 4) if tmp > 31 else (tmp, 3) for tmp in (s2 - 2, s2 + 1)]
    dates[1:1] = tmp
    return [datetime.date(year, month, day) for day, month in dates]

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
