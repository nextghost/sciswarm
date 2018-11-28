# -*- coding: utf-8 -*-
from django.utils.translation import (ugettext_lazy as _, pgettext_lazy,
    ungettext_lazy)
from collections import OrderedDict

__all__ = []

class ConstEnum(OrderedDict):
    def __init__(self, *items):
        super(ConstEnum, self).__init__()
        self._plural = dict()
        for item in items:
            name, code, desc = item[:3]
            if name.startswith('_'):
                raise ValueError('Invalid attribute name')
            self.__setattr__(name, code)
            super(ConstEnum, self).__setitem__(code, desc)
            if len(item) > 3:
                self._plural[code] = item[3]

    def plural(self, code):
        return self._plural[code]

    def __setitem__(self, name, value):
        msg = "'{0}' object is read-only".format(self.__class__.__name__)
        raise KeyError(msg)

person_alias_schemes = ConstEnum(
    ('EMAIL', 'mailto', _('E-mail')),
    ('ORCID', 'orcid', _('ORCID iD')),
    ('XMPP', 'xmpp', _('XMPP')),
    ('TWITTER', 'twitter', _('Twitter')),
    ('SCISWARM', 'swarm', _('Sciswarm')),
    ('URL', 'http', _('Personal website')),
    ('OTHER', '', _('Other')),
)

paper_alias_schemes = ConstEnum(
    ('DOI', 'doi', _('DOI')),
    ('ISBN', 'isbn', _('ISBN')),
    ('ARXIV', 'arxiv', _('arXiv')),
    ('SCISWARM', 'swarm', _('Sciswarm')),
    ('URL', 'http', _('Web URL')),
    ('OTHER', '', _('Other')),
)
