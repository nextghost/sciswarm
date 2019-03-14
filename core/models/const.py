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

from django.utils.translation import (ugettext_lazy as _, pgettext_lazy,
    ungettext_lazy)
from collections import OrderedDict

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

paper_quality_ratings = ConstEnum(
    ('BAD', 0, _('Questionable')),
    ('MIXED', 1, _('Mixed')),
    ('GOOD', 2, _('Rigorous')),
)

paper_importance_ratings = ConstEnum(
    ('LOW', 0, _('Waste of time')),
    ('MEDIUM', 1, _('Average')),
    ('HIGH', 2, _('Revolutionary')),
)

user_feed_events = ConstEnum(
    ('PAPER_POSTED', 0, _('{person} has posted a new paper: {paper}')),
    ('AUTHORSHIP_CONFIRMED', 1,
        _('{person} has confirmed authorship of {paper}')),
    ('PAPER_REVIEW', 2, _('{person} has posted a review of {paper}')),
    ('PAPER_RECOMMENDATION', 3, _('{person} recommends paper: {paper}')),
)

feed_subscription_types = ConstEnum(
    ('PAPERS', 0, _('New papers')),
    ('REVIEWS', 1, _('Paper reviews')),
    ('RECOMMENDATIONS', 2, _('Recommendations')),
)

science_fields = ConstEnum(
    ('ASTRONOMY', 1, _('Astronomy')),
    ('BIOLOGY', 2, _('Biology')),
    ('CHEMISTRY', 3, _('Chemistry')),
    ('COMPSCI', 4, _('Computer Science')),
    ('GEO', 5, _('Earth Science')),
    ('ENGINEERING', 6, _('Engineering')),
    ('HISTORY', 7, _('History')),
    ('MATH', 8, _('Mathematics')),
    ('MEDICINE', 9, _('Medicine')),
    ('PHILOSOPHY', 10, _('Philosophy')),
    ('PHYSICS', 11, _('Physics')),
    ('SOCIAL', 12, _('Social Science')),
)
