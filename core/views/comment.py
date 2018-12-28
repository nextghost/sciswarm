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

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import prefetch_related_objects, aggregates
from django.db.transaction import atomic
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView
from ..forms.comment import PaperReviewForm, PaperReviewResponseForm
from .base import (BaseCreateView, BaseUpdateView, BaseListView,
    SearchListView, BaseModelFormsetView, BaseDeleteView, BaseUnlinkAliasView)
from .utils import paper_navbar, PageNavigator
from .. import models

class PaperReviewListView(BaseListView):
    template_name = 'core/comment/paperreview_list.html'

    # TODO: Pin the current user's own review at the top of first page
    def get_queryset(self):
        qs = models.Paper.objects.filter_public()
        self.paper = get_object_or_404(qs, pk=self.kwargs['pk'])
        table = models.PaperReview.query_model
        response_count = aggregates.Count(table.paperreviewresponse.pk.f())
        qs = self.paper.paperreview_set.filter_public()
        qs = qs.select_related('posted_by')
        return qs.annotate(response_count=response_count)

    def get_context_data(self, *args, **kwargs):
        ret = super(PaperReviewListView, self).get_context_data(*args,**kwargs)
        ret['page_title'] = _('Paper Reviews: %s') % str(self.paper)
        ret['is_paper_author'] = False
        ret['user_person'] = None
        if self.request.user.is_authenticated:
            ret['is_paper_author'] = self.paper.is_author(self.request.user)
            ret['user_person'] = self.request.user.person
        ret['navbar'] = paper_navbar(self.request, self.paper)
        return ret

class PaperReviewDetailView(DetailView):
    queryset = models.PaperReview.objects.filter_public().select_related(
        'paper', 'posted_by')
    template_name = 'core/comment/paperreview_detail.html'

    def get_context_data(self, *args, **kwargs):
        ret = super(PaperReviewDetailView, self).get_context_data(*args,
            **kwargs)
        user = self.request.user
        obj = ret['object']
        qs = obj.paperreviewresponse_set.select_related('posted_by')
        pagenav = PageNavigator(self.request, qs, 50)
        ret['response_list'] = pagenav.page.object_list
        ret['reply_access'] = False
        ret['user_person'] = None
        if user.is_authenticated:
            is_author = obj.paper.is_author(user)
            ret['reply_access'] = is_author or (obj.posted_by == user.person)
            ret['user_person'] = self.request.user.person
        ret['navbar'] = paper_navbar(self.request, obj.paper)
        ret['paginator'] = pagenav
        return ret

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class CreatePaperReviewView(BaseCreateView):
    form_class = PaperReviewForm
    template_name = 'core/comment/paperreview_form.html'
    page_title = _('Review Paper')

    def get_initial(self):
        ret = super(CreatePaperReviewView, self).get_initial()
        qs = models.Paper.objects.filter_public().select_related('posted_by')
        paper = get_object_or_404(qs, pk=self.kwargs['pk'])
        if paper.is_author(self.request.user):
            raise PermissionDenied(_('You cannot review your own paper.'))
        # Don't allow posting even if the previous review was deleted.
        qs = paper.paperreview_set.filter_by_author(self.request.user.person)
        if qs.exists():
            msg = _('You cannot review a paper more than once.')
            raise PermissionDenied(msg)
        ret['paper'] = paper
        self.paper = paper
        return ret

    def get_form_kwargs(self, *args, **kwargs):
        ret = super(CreatePaperReviewView, self).get_form_kwargs(*args,
            **kwargs)
        ret['user'] = self.request.user
        return ret

    def get_context_data(self, *args, **kwargs):
        ret = super(CreatePaperReviewView, self).get_context_data(*args,
            **kwargs)
        ret['paper'] = self.paper
        return ret

    def get_success_url(self):
        kwargs = dict(pk=self.paper.pk)
        return reverse('core:paperreview_list', kwargs=kwargs)

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class UpdatePaperReviewView(BaseUpdateView):
    queryset = models.PaperReview.objects.filter_public().select_related(
        'paper', 'posted_by')
    form_class = PaperReviewForm
    template_name = 'core/comment/paperreview_form.html'
    page_title = _('Edit Paper Review')

    def get_object(self, *args, **kwargs):
        ret = super(UpdatePaperReviewView, self).get_object(*args, **kwargs)
        if self.request.user.person != ret.posted_by:
            msg =_("You cannot edit somebody else's review.")
            raise PermissionDenied(msg)
        return ret

    def get_success_url(self):
        kwargs = dict(pk=self.object.paper.pk)
        return reverse('core:paperreview_list', kwargs=kwargs)

@method_decorator(login_required, name='dispatch')
class DeletePaperReviewView(BaseDeleteView):
    queryset = models.PaperReview.objects.filter_public().select_related(
        'paper', 'posted_by')
    template_name = 'core/comment/delete_paperreview.html'
    
    def get_object(self, *args, **kwargs):
        ret = super(DeletePaperReviewView, self).get_object(*args, **kwargs)
        if self.request.user.person != ret.posted_by:
            msg =_("You cannot delete somebody else's review.")
            raise PermissionDenied(msg)
        return ret

    def perform_delete(self):
        self.object.deleted = True
        self.object.save(update_fields=['deleted', 'date_changed'])

    def get_success_url(self):
        kwargs = dict(pk=self.object.paper.pk)
        return reverse('core:paperreview_list', kwargs=kwargs)

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class CreatePaperReviewResponseMainView(BaseCreateView):
    form_class = PaperReviewResponseForm
    template_name = 'core/comment/paperreviewresponse_form.html'
    page_title = _('Respond to Paper Review')

    def get_parent(self):
        qs = models.PaperReview.objects.filter_public()
        qs = qs.select_related('paper__posted_by', 'posted_by')
        parent = get_object_or_404(qs, pk=self.kwargs['pk'])
        self.parent = parent
        self.comment = parent
        return parent

    def get_initial(self):
        ret = super(CreatePaperReviewResponseMainView, self).get_initial()
        parent = self.get_parent()
        user = self.request.user
        is_author = parent.paper.is_author(user)
        if not (is_author or (parent.posted_by == user.person)):
            raise PermissionDenied(_('You cannot reply to this review.'))
        ret['parent'] = parent
        return ret

    def get_form_kwargs(self, *args, **kwargs):
        ret = super(CreatePaperReviewResponseMainView, self).get_form_kwargs(
            *args, **kwargs)
        ret['user'] = self.request.user
        return ret

    def get_context_data(self, *args, **kwargs):
        ret = super(CreatePaperReviewResponseMainView, self).get_context_data(
            *args, **kwargs)
        ret['parent'] = self.parent
        ret['comment'] = self.comment
        return ret

    def get_success_url(self):
        return self.parent.get_absolute_url()

# Decorators applied in parent view
class CreatePaperReviewResponseSubView(CreatePaperReviewResponseMainView):
    def get_parent(self):
        qs = models.PaperReviewResponse.objects.filter_public()
        qs = qs.select_related('parent__paper__posted_by', 'parent__posted_by',
            'posted_by')
        comment = get_object_or_404(qs, pk=self.kwargs['pk'])
        self.parent = comment.parent
        self.comment = comment
        return comment.parent

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class UpdatePaperReviewResponseView(BaseUpdateView):
    queryset = models.PaperReviewResponse.objects.filter_public().select_related('parent', 'posted_by')
    form_class = PaperReviewResponseForm
    page_title = _('Edit Response')

    def get_object(self, *args, **kwargs):
        ret = super(UpdatePaperReviewResponseView, self).get_object(*args,
            **kwargs)
        if ret.posted_by != self.request.user.person:
            msg = _("You cannot edit somebody else's comment.")
            raise PermissionDenied(msg)
        return ret

    def get_form_kwargs(self, *args, **kwargs):
        ret = super(UpdatePaperReviewResponseView, self).get_form_kwargs(*args,
            **kwargs)
        ret['user'] = self.request.user
        return ret

    def get_success_url(self):
        return self.object.parent.get_absolute_url()

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class DeletePaperReviewResponseView(BaseDeleteView):
    queryset = models.PaperReviewResponse.objects.filter_public().select_related('posted_by')
    template_name = 'core/comment/delete_paperreviewresponse.html'

    def get_object(self, *args, **kwargs):
        ret = super(DeletePaperReviewResponseView, self).get_object(*args,
            **kwargs)
        if ret.posted_by != self.request.user.person:
            msg = _("You cannot delete somebody else's comment.")
            raise PermissionDenied(msg)
        return ret

    def get_success_url(self):
        return self.object.parent.get_absolute_url()
