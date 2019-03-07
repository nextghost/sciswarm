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

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _, get_language
from .base import BaseListView
from ..models import const
from ..utils import sql, utils
from .. import models

def homepage(request):
    if request.user.is_authenticated:
        return UserTimelineView.as_view()(request)
    context = dict(admin_email=settings.SYSTEM_EMAIL_ADMIN)
    return render(request, 'core/main/homepage.html', context)

def infopage(request, pagename):
    tpl = 'core/info/%(lang)s/%(pagename)s.html'
    lang = request.GET.get('lang', get_language() or setting.LANGUAGE_CODE)
    if lang not in set((c for c,n in settings.LANGUAGES)):
        raise Http404()
    template_name = tpl % dict(lang=lang, pagename=pagename)
    context = dict(admin_email=settings.SYSTEM_EMAIL_ADMIN)
    return render(request, template_name, context)

def help_page(request, pagename='index'):
    template_name = 'core/help/%s.html' % pagename
    return render(request, template_name, dict())

@method_decorator(login_required, name='dispatch')
class UserTimelineView(BaseListView):
    template_name = 'core/event/feed_detail.html'
    paginate_by = 100

    def get_queryset(self):
        evtab = sql.Table(models.FeedEvent)
        stab = sql.Table(models.FeedSubscription)
        evtypes = const.user_feed_events
        subtypes = const.feed_subscription_types
        person_id = self.request.user.person_id
        type_map = {
            subtypes.PAPERS: [evtypes.PAPER_POSTED,
                evtypes.AUTHORSHIP_CONFIRMED],
            subtypes.REVIEWS: evtypes.PAPER_REVIEW,
            subtypes.RECOMMENDATIONS: evtypes.PAPER_RECOMMENDATION,
        }

        # Subscription subquery
        cond_list = []
        for subscription, events in type_map.items():
            tmp = (stab.subscription_type == subscription)
            if isinstance(events, (list, tuple)):
                tmp &= evtab.event_type.belongs(events)
            else:
                tmp &= (evtab.event_type == events)
            cond_list.append(tmp)
        query = (evtab.person_id == stab.poster_id) & utils.fold_or(cond_list)
        join = evtab.left_join(stab, query)
        where = ((evtab.person_id == person_id) |
            (stab.follower_id == person_id))
        event_subq = join.select(evtab.pk, where=where)

        # Main queryset
        feedtab = models.FeedEvent.query_model
        poster_subq = models.Person.objects.filter_active().values_list('pk')
        query = (feedtab.pk.belongs(event_subq) &
            feedtab.person.pk.belongs(poster_subq))
        return models.FeedEvent.objects.filter(query).select_related('person',
            'paper')

    def get_context_data(self, *args, **kwargs):
        ret = super(UserTimelineView, self).get_context_data(*args, **kwargs)
        ret['page_title'] = _('Timeline')
        return ret
