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

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.transaction import atomic
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from .base import BaseListView
from .utils import person_navbar
from .. import models

class PersonEventFeed(BaseListView):
    template_name = 'core/event/feed_detail.html'
    paginate_by = 100

    def get_queryset(self):
        qs = models.Person.objects.filter_active()
        qs = qs.filter_username(self.kwargs['username'])
        self.person = get_object_or_404(qs)
        return self.person.feedevent_set.select_related('person', 'paper')

    def get_context_data(self, *args, **kwargs):
        ret = super(PersonEventFeed, self).get_context_data(*args, **kwargs)
        ret['person'] = self.person
        ret['page_title'] = _('Latest Actions of %s') % self.person.full_name
        ret['navbar'] = person_navbar(self.request, self.kwargs['username'],
            self.person)
        return ret
