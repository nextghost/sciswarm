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

from django.core import validators
from django.forms import ValidationError
from django.utils.translation import ugettext as _
from ..models import const
from .. import models
import re

def sciswarm_person_id_validator(value):
    if not value.startswith('u/'):
        raise ValidationError(_('Invalid Sciswarm user identifier.'),'invalid')
    ident = value[2:]
    query = (models.User.query_model.username == ident)
    if not models.User.objects.filter_active().filter(query).exists():
        raise ValidationError(_('This user does not exist.'), 'invalid')

def sciswarm_paper_id_validator(value):
    if not value.startswith('p/'):
        msg = _('Invalid Sciswarm paper identifier.')
        raise ValidationError(msg, 'invalid')
    try:
        pk = int(value[2:])
    except ValueError:
        raise ValidationError(invalid_msg, 'invalid')
    query = (models.Paper.query_model.pk == pk)
    if not models.Paper.objects.filter_public().filter(query).exists():
        raise ValidationError(_('This paper does not exist.'), 'invalid')

def sciswarm_id_validator(value):
    if value.startswith('u/'):
        return sciswarm_person_id_validator(value)
    elif value.startswith('p/'):
        return sciswarm_paper_id_validator(value)
    else:
        invalid_msg = _('Invalid Sciswarm identifier.')
        raise ValidationError(invalid_msg, 'invalid')

def isni_validator(value):
    if not re.match(r'^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]$', value):
        raise ValidationError(_('Invalid identifier format.'), 'invalid')
    total = 0
    for digit in value[:-1]:
        if digit == '-':
            continue
        total = (total + int(digit)) * 2
    checksum = (12 - total % 11) % 11
    if checksum == 10:
        checksum = 'X'
    if value[-1] != str(checksum):
        raise ValidationError(_('Identifier checksum is incorrect.'),'invalid')

def isbn_validator(value):
    err = ValidationError(_('Invalid identifier format.'), 'invalid')
    if not re.match(r'^(?:97[89]-?)?[0-9]+(?:-[0-9]+){0,2}-?[0-9X]$', value):
        raise err
    number = value.replace('-', '')
    if len(number) == 13:
        total = sum((int(x)*y for x,y in zip(number[:-1], [1,3]*6)))
        checksum = 10 - total % 10
        if checksum == 10:
            checksum = 0
    elif len(number) == 10:
        total = sum((int(x)*y for x,y in zip(number[:-1], range(10, 1, -1))))
        checksum = (11 - total % 11) % 11
        if checksum == 10:
            checksum = 'X'
    else:
        raise err
    if value[-1] != str(checksum):
        raise ValidationError(_('Identifier checksum is incorrect.'),'invalid')

def arxiv_validator(value):
    pattern = r'^(?:arXiv:)?((?:[0-9]{4}\.[0-9]{4,5}|[a-z][a-z-]*(?:\.[A-Z]+)/[0-9]{7})(?:v[0-9]+)?)$'
    result = re.match(pattern, value)
    if not result:
        raise ValidationError(_('Invalid identifier format.'), 'invalid')
    return result.group(1)

_person_alias_validator_map = {
    const.person_alias_schemes.EMAIL: validators.validate_email,
    const.person_alias_schemes.ORCID: isni_validator,
    # FIXME: Write a proper RFC7622 validator
    const.person_alias_schemes.XMPP: validators.validate_email,
    const.person_alias_schemes.TWITTER:
        validators.RegexValidator(r'^@[a-zA-Z0-9_]{1,15}$'),
    const.person_alias_schemes.SCISWARM: sciswarm_person_id_validator,
    const.person_alias_schemes.URL: validators.URLValidator(),
}

_paper_alias_validator_map = {
    const.person_alias_schemes.SCISWARM: sciswarm_paper_id_validator,
    const.person_alias_schemes.URL: validators.URLValidator(),
    const.paper_alias_schemes.DOI:
        validators.RegexValidator(r'^10\.[0-9]{4,}(?:\.[0-9]+)*/.*'),
    const.paper_alias_schemes.ISBN: isbn_validator,
    const.paper_alias_schemes.ARXIV: arxiv_validator,
}

_alias_validator_map = {
    const.person_alias_schemes.EMAIL: validators.validate_email,
    const.person_alias_schemes.ORCID: isni_validator,
    # FIXME: Write a proper RFC7622 validator
    const.person_alias_schemes.XMPP: validators.validate_email,
    const.person_alias_schemes.TWITTER:
        _person_alias_validator_map[const.person_alias_schemes.TWITTER],
    const.person_alias_schemes.SCISWARM: sciswarm_id_validator,
    const.person_alias_schemes.URL: validators.URLValidator(),
    const.paper_alias_schemes.DOI:
        _paper_alias_validator_map[const.paper_alias_schemes.DOI],
    const.paper_alias_schemes.ISBN: isbn_validator,
    const.paper_alias_schemes.ARXIV: arxiv_validator,
}

def _validate_alias(validator_map, scheme, identifier):
    if not scheme:
        url_schemes = r'^(https?|ftps?)://'
        if re.match(url_schemes, identifier.lower()):
            scheme = const.person_alias_schemes.URL
        else:
            tokens = identifier.split(':', 1)
            if len(tokens) != 2 or not tokens[0]:
                msg = _('Generic identifier must have a scheme prefix separated by color (e.g. scheme:identifier).')
                raise ValidationError(msg, 'invalid')
            (scheme, identifier) = tokens
    scheme = scheme.lower()
    valfunc = validator_map.get(scheme)
    if valfunc is not None:
        ret = valfunc(identifier)
        if ret is not None:
            identifier = ret
    return (scheme, identifier)

def validate_person_alias(scheme, identifier):
    return _validate_alias(_person_alias_validator_map, scheme, identifier)

def validate_paper_alias(scheme, identifier):
    return _validate_alias(_paper_alias_validator_map, scheme, identifier)

def validate_alias(scheme, identifier):
    return _validate_alias(_alias_validator_map, scheme, identifier)
