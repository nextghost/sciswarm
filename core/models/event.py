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

from django.db import models, transaction, IntegrityError
from django.urls import reverse
from django.utils.html import format_html, mark_safe
from django.utils.translation import ugettext_lazy as _
from ..utils import html
from . import const, paper

class FeedEvent(models.Model):
    class Meta:
        ordering = ('-pk',)

    default_message = _('{person} did something with paper {paper}')

    person = models.ForeignKey(paper.Person, verbose_name=_('person'),
        on_delete=models.CASCADE, editable=False)
    paper = models.ForeignKey(paper.Paper, verbose_name=_('paper'),
        on_delete=models.CASCADE, editable=False)
    event_date = models.DateTimeField(_('event date'), auto_now_add=True,
        db_index=True, editable=False)
    event_type = models.IntegerField(_('event type'),
        choices=const.user_feed_events.items(), db_index=True, editable=False)

    def __str__(self):
        msg = const.user_feed_events.get(self.event_type, self.default_message)
        return msg.format(person=self.person.plain_name, paper=self.paper)

    def __html__(self):
        msg = const.user_feed_events.get(self.event_type, self.default_message)
        paper = html.render_link(self.paper.get_absolute_url(),str(self.paper))
        return format_html(msg, person=self.person.__html__(), paper=paper)

class FeedSubscription(models.Model):
    class Meta:
        ordering = ('-pk',)
        unique_together = ('follower', 'subscription_type', 'poster')
    poster = models.ForeignKey(paper.Person, verbose_name=_('person'),
        on_delete=models.CASCADE, editable=False, related_name='follower_set',
        related_query_name='follower')
    follower = models.ForeignKey(paper.Person, verbose_name=_('person'),
        on_delete=models.CASCADE, editable=False)
    subscription_type = models.IntegerField(_('event type'),
        choices=const.feed_subscription_types.items(), db_index=True,
        editable=False)
