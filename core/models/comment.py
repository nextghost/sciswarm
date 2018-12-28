# This file is part of Sciswarm, a scientific social network
# Copyright (C) 2018 Martin Doucha
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
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from . import const, paper

class CommentManager(models.Manager):
    def filter_by_author(self, person):
        query = (self.model.query_model.posted_by == person)
        return self.filter(query)

class BaseComment(models.Model):
    class Meta:
        abstract = True
    objects = CommentManager()

    date_posted = models.DateTimeField(_('date posted'), auto_now_add=True,
        db_index=True, editable=False)
    date_changed = models.DateTimeField(_('date changed'), auto_now=True,
        db_index=True, editable=False)
    posted_by = models.ForeignKey(paper.Person, verbose_name=_('posted by'),
        null=True, on_delete=models.SET_NULL, editable=False)
    message = models.TextField(_('message'), max_length=10000)

class PaperReviewManager(CommentManager):
    def filter_public(self):
        table = self.model.query_model
        query = ((table.deleted == False) & (table.paper.public == True))
        return self.filter(query)

class PaperReview(BaseComment):
    class Meta:
        ordering = ('paper', '-date_posted',)
        unique_together = (('paper', 'posted_by'),)
    objects = PaperReviewManager()

    paper = models.ForeignKey(paper.Paper, verbose_name=_('paper'),
        on_delete=models.PROTECT, editable=False)
    methodology = models.IntegerField(_('methodology'),
        choices=const.paper_quality_ratings.items(),
        help_text=_('Quality of methodology. If about half of the conclusions are invalid due to methodology errors, choose "Mixed".'))
    importance = models.IntegerField(_('importance'),
        choices=const.paper_importance_ratings.items(),
        help_text=_('How much attention this paper deserves, not just for its conclusions but also for new methodologies or any other revolutionary scientific ideas.'))
    deleted = models.BooleanField(_('deleted'), editable=False, db_index=True,
        default=False)

    def get_absolute_url(self):
        return reverse('core:paperreview_detail', kwargs=dict(pk=self.pk))

class PaperReviewResponseManager(CommentManager):
    def filter_public(self):
        parent = self.model.query_model.parent
        query = ((parent.deleted == False) & (parent.paper.public == True))
        return self.filter(query)

class PaperReviewResponse(BaseComment):
    class Meta:
        ordering = ('parent', '-date_posted')
    objects = PaperReviewResponseManager()

    parent = models.ForeignKey(PaperReview, verbose_name=_('review'),
        on_delete=models.PROTECT, editable=False)
