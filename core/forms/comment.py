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

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext_lazy as _
from .base import Form, ModelForm, BaseAliasForm
from ..models import const
from ..utils.transaction import lock_record
from .. import models

class PaperReviewForm(ModelForm):
    class Meta:
        model = models.PaperReview
        fields = ('methodology', 'importance', 'message')

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(PaperReviewForm, self).__init__(*args, **kwargs)
        if self.instance.pk is None:
            if self.user is None:
                msg = '"user" keyword argument is required'
                raise ImproperlyConfigured(msg)
            paper = self.initial.get('paper')
            if paper is None:
                msg = '"paper" initial value is required'
                raise ImproperlyConfigured(msg)
            self.instance.paper = paper
            self.instance.posted_by = self.user.person
        self.fields['message'].label = _('Details')

    def clean(self):
        if self.instance.pk is not None:
            # Prevent race condition with deletion view
            tmp = lock_record(self.instance, ['paper'])
            if tmp is None:
                msg = _('Database error, please try again later.')
                raise ValidationError(msg, 'lock')
            if tmp.deleted:
                msg = _('This review has been deleted.')
                raise ValidationError(msg, 'deleted')
            self.instance = tmp
        else:
            paper = lock_record(self.instance.paper)
            if paper is None:
                msg = _('Database error, please try again later.')
                raise ValidationError(msg, 'lock')
            if paper.is_author(self.user):
                msg = _('You cannot review your own paper.')
                raise ValidationError(msg, 'selfpromo')
            qs = paper.paperreview_set
            # Don't allow posting even if the previous review was deleted.
            if qs.filter_by_author(self.instance.posted_by).exists():
                msg = _('You cannot review a paper more than once.')
                raise ValidationError(msg, 'unique')

    def save(self):
        ret = super(PaperReviewForm, self).save()
        models.FeedEvent.objects.create(person=ret.posted_by, paper=ret.paper,
            event_type=const.user_feed_events.PAPER_REVIEW)
        return ret

    save.alters_data = True

class PaperReviewResponseForm(ModelForm):
    class Meta:
        model = models.PaperReviewResponse
        fields = ('message',)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(PaperReviewResponseForm, self).__init__(*args, **kwargs)
        if self.instance.pk is None:
            if self.user is None:
                msg = '"user" keyword argument is required'
                raise ImproperlyConfigured(msg)
            parent = self.initial.get('parent')
            if parent is None:
                msg = '"parent" initial value is required'
                raise ImproperlyConfigured(msg)
            self.instance.parent = parent
            self.instance.posted_by = self.user.person

    def clean(self):
        if self.instance.pk is None:
            parent = lock_record(self.instance.parent)
            if parent is None:
                msg = _('Database error, please try again later.')
                raise ValidationError(msg, 'lock')
