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
from django.db import IntegrityError
from django.db.models import prefetch_related_objects
from django.db.transaction import atomic
from django.forms import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView
from .base import (BaseCreateView, BaseUpdateView, BaseListView,
    SearchListView, BaseModelFormsetView, BaseDeleteView, BaseUnlinkAliasView)
from ..forms.paper import (PaperSearchForm, PaperForm, PaperAliasForm,
    PaperAliasFormset, PaperAuthorNameFormset)
from ..forms.user import (PaperAuthorForm, UserAliasForm, UserAliasFormset,
    AuthorshipConfirmationForm)
from ..utils.html import NavigationBar
from ..utils.utils import list_map, logger, remove_duplicates
from .. import models

class PaperListView(SearchListView):
    queryset = models.Paper.objects.filter_public()
    form_class = PaperSearchForm
    template_name = 'core/paper/paper_list.html'
    page_title = _('Latest papers')

    def get_context_data(self, *args, **kwargs):
        ret = super(PaperListView, self).get_context_data(*args, **kwargs)
        obj_list = list(ret['object_list'])
        refs = models.PaperAuthorReference.objects.filter_unrejected(obj_list)
        refs = refs.select_related('author_alias__target')
        ref_map = list_map(((x.paper_id, x) for x in refs))
        antab = models.PaperAuthorName.query_model
        query = antab.paper.belongs(obj_list)
        names = models.PaperAuthorName.objects.filter(query)
        name_map = list_map(((x.paper_id,x) for x in names))
        ret['object_list'] = [(x, ref_map.get(x.pk,[]), name_map.get(x.pk,[]))
            for x in obj_list]
        ret['page_title'] = self.page_title
        ret['navbar'] = ''
        return ret

class CitedByPaperListView(PaperListView):
    def get_base_queryset(self):
        table = models.Paper.query_model
        qs = models.Paper.objects.filter_public()
        self.paper = get_object_or_404(qs, pk=self.kwargs['pk'])
        query = (table.bibliography.target == self.paper)
        return models.Paper.objects.filter_public().filter(query).distinct()

    def get_context_data(self, *args, **kwargs):
        ret = super(CitedByPaperListView, self).get_context_data(*args,
            **kwargs)
        ret['page_title'] = _('Papers Citing: %s') % self.paper.name
        return ret

class UserPostedPaperListView(PaperListView):
    def get_base_queryset(self):
        qs = models.User.objects
        self.user = get_object_or_404(qs, username=self.kwargs['username'])
        return self.user.posted_paper_set.filter_public()

    def get_context_data(self, *args, **kwargs):
        ret = super(UserPostedPaperListView, self).get_context_data(*args,
            **kwargs)
        ret['page_title'] = _('Papers Posted by %s') % self.user.full_name
        return ret

class UserAuthoredPaperListView(PaperListView):
    def get_base_queryset(self):
        qs = models.User.objects
        self.user = get_object_or_404(qs, username=self.kwargs['username'])
        reftab = models.Paper.query_model.paperauthorreference
        # Show only confirmed papers
        query = ((reftab.author_alias.target == self.user) &
            (reftab.confirmed == True))
        return models.Paper.objects.filter_public().filter(query).distinct()

    def get_context_data(self, *args, **kwargs):
        ret = super(UserAuthoredPaperListView, self).get_context_data(*args,
            **kwargs)
        ret['page_title'] = _('Papers by %s') % self.user.full_name
        return ret

@method_decorator(login_required, name='dispatch')
class RejectedAuthorshipPaperListView(PaperListView):
    page_title = _('Papers You Have Rejected')

    def get_base_queryset(self):
        reftab = models.Paper.query_model.paperauthorreference
        query = ((reftab.author_alias.target == self.request.user) &
            (reftab.confirmed == False))
        return models.Paper.objects.filter_public().filter(query).distinct()

    def get_context_data(self, *args, **kwargs):
        ret = super(RejectedAuthorshipPaperListView, self).get_context_data(
            *args, **kwargs)
        links = [(_('Manage authorship'), 'core:mass_authorship_confirmation',
            tuple(), dict())]
        ret['navbar'] = NavigationBar(self.request, links)
        return ret

class PaperDetailView(DetailView):
    queryset = models.Paper.objects.select_related('posted_by', 'changed_by')
    template_name = 'core/paper/paper_detail.html'

    def get_object(self, *args, **kwargs):
        ret = super(PaperDetailView, self).get_object(*args, **kwargs)
        if not ret.public:
            # FIXME: Change to HTTP error 451
            msg = _('This paper is not available for legal reasons.')
            raise PermissionDenied(msg)
        return ret

    def get_context_data(self, *args, **kwargs):
        ret = super(PaperDetailView, self).get_context_data(*args, **kwargs)
        obj = ret['object']
        links = [
            (_('Cited by'), 'core:cited_by_paper_list', tuple(),
                dict(pk=obj.pk)),
        ]
        qs = models.PaperAuthorReference.objects.filter_unrejected(obj)
        ret['author_list'] = qs.select_related('author_alias__target')
        ret['author_names'] = obj.paperauthorname_set.all()
        ret['bibliography'] = obj.bibliography.all()
        ret['keyword_list'] = obj.paperkeyword_set.all()
        ret['alias_list'] = obj.paperalias_set.all()
        ret['edit_access'] = False
        if self.request.user.is_authenticated:
            edit_access = obj.is_owned_by(self.request.user)
            ret['edit_access'] = edit_access
            if edit_access:
                links.append((_('Edit'), 'core:edit_paper', tuple(),
                    dict(pk=obj.pk)))
            uatab = models.UserAlias.query_model
            query = (uatab.target == self.request.user)
            if obj.authors.filter(query).exists():
                links.append((_('Manage authorship'),
                    'core:paper_authorship_confirmation', tuple(),
                    dict(pk=obj.pk)))
        navbar = ''
        if links:
            navbar = NavigationBar(self.request, links)
        ret['navbar'] = navbar
        # FIXME: show papers citing this one?
        return ret

@method_decorator(login_required, name='dispatch')
class CreatePaperView(BaseCreateView):
    form_class = PaperForm
    template_name = 'core/paper/create_paper.html'
    page_title = _('Create Paper')

    def get_form(self, *args, **kwargs):
        ret = super(CreatePaperView, self).get_form(*args, **kwargs)
        data = self.request.POST or None
        subforms = dict()
        subforms['authors'] = UserAliasFormset(data, prefix='authors',
            queryset=models.UserAlias.objects.none(),
            form_kwargs=dict(label=_('Author:'), allow_sciswarm=True))
        subforms['authors'].extra = 5
        subforms['author_names'] = PaperAuthorNameFormset(data,
            queryset=models.PaperAuthorName.objects.none(),
            prefix='author_names')
        subforms['author_names'].extra = 5
        no_alias_qs = models.PaperAlias.objects.none()
        subforms['aliases'] = PaperAliasFormset(data, prefix='aliases',
            queryset=no_alias_qs, form_kwargs=dict(require_unlinked=True))
        subforms['aliases'].extra = 5
        subforms['bibliography'] = PaperAliasFormset(data,
            prefix='bibliography', queryset=no_alias_qs,
            form_kwargs=dict(label=_('Biblio entry:'), allow_sciswarm=True))
        subforms['bibliography'].extra = 20
        self.subforms = subforms
        return ret

    def post(self, *args, **kwargs):
        self.object = None
        form = self.get_form()
        formlist = [form, *self.subforms.values()]
        if all((x.is_valid() for x in formlist)):
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        form.instance.posted_by = self.request.user
        form.instance.changed_by = self.request.user
        try:
            with atomic():
                ret = super(CreatePaperView, self).form_valid(form)
                for subform in self.subforms['aliases']:
                    subform.instance.target = self.object
                self.subforms['aliases'].save()
                authors = self.subforms['authors'].save()
                ref_cls = models.PaperAuthorReference
                author_refs = [ref_cls(paper=self.object, author_alias=x)
                    for x in authors]
                ref_cls.objects.bulk_create(author_refs)
                for subform in self.subforms['author_names']:
                    subform.instance.paper = self.object
                self.subforms['author_names'].save()
                biblio = self.subforms['bibliography'].save()
                self.object.bibliography.add(*biblio)
                return ret
        except IntegrityError:
            logger.info('Race condition detected while linking paper alias.',
                exc_info=False)
            return self.form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, *args, **kwargs):
        ret = super(CreatePaperView, self).get_context_data(*args, **kwargs)
        ret.update(self.subforms)
        return ret

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class UpdatePaperView(BaseUpdateView):
    queryset = models.Paper.objects.select_related('posted_by')
    form_class = PaperForm
    page_title = _('Edit Paper')

    def get_object(self, *args, **kwargs):
        ret = super(UpdatePaperView, self).get_object(*args, **kwargs)
        if not ret.is_owned_by(self.request.user):
            raise PermissionDenied(_('You are not one of the authors.'))
        return ret

    def form_valid(self, form):
        form.instance.changed_by = self.request.user
        return super(UpdatePaperView, self).form_valid(form)

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class AddPaperAuthorView(BaseCreateView):
    form_class = PaperAuthorForm
    page_title = _('Add Paper Author')

    def get_form_kwargs(self, *args, **kwargs):
        qs = models.Paper.objects
        if self.request.method == 'POST':
            qs = qs.select_for_update()
        paper = get_object_or_404(qs, pk=self.kwargs['pk'])
        if not paper.is_owned_by(self.request.user):
            raise PermissionDenied(_('You are not one of the authors.'))
        self.parent = paper
        ret = super(AddPaperAuthorView, self).get_form_kwargs(*args, **kwargs)
        ret['paper'] = paper
        return ret

    def form_valid(self, form):
        ret = super(AddPaperAuthorView, self).form_valid(form)
        self.parent.changed_by = self.request.user
        self.parent.save(update_fields=['last_changed', 'changed_by'])
        return ret

    def get_success_url(self):
        return self.parent.get_absolute_url()

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class DeletePaperAuthorView(BaseDeleteView):
    queryset = models.PaperAuthorReference.objects.select_related('paper')
    template_name = 'core/paper/delete_paper_author.html'

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        if self.request.method == 'POST':
            queryset = queryset.select_for_update()
        ret = super(DeletePaperAuthorView, self).get_object(queryset)
        prefetch_related_objects([ret], 'author_alias__target',
            'paper__posted_by')
        if not ret.paper.is_owned_by(self.request.user):
            raise PermissionDenied(_('You are not one of the authors.'))
        elif ret.confirmed is False:
            raise PermissionDenied(_('Rejected authorship cannot be deleted.'))
        return ret

    def perform_delete(self):
        super(DeletePaperAuthorView, self).perform_delete()
        self.object.paper.changed_by = self.request.user
        self.object.paper.save(update_fields=['last_changed', 'changed_by'])

    def get_success_url(self):
        return self.object.paper.get_absolute_url()

class DeletePaperAuthorNameView(BaseDeleteView):
    queryset = models.PaperAuthorName.objects.select_related('paper__posted_by')
    template_name = 'core/paper/delete_paper_author_name.html'

    def get_object(self, *args, **kwargs):
        ret = super(DeletePaperAuthorNameView, self).get_object(*args,**kwargs)
        if not ret.paper.is_owned_by(self.request.user):
            raise PermissionDenied(_('You are not one of the authors.'))
        return ret

    def perform_delete(self):
        super(DeletePaperAuthorNameView, self).perform_delete()
        self.object.paper.changed_by = self.request.user
        self.object.paper.save(update_fields=['last_changed', 'changed_by'])

    def get_success_url(self):
        return self.object.paper.get_absolute_url()

@method_decorator(login_required, name='dispatch')
class LinkPaperAliasView(BaseCreateView):
    form_class = PaperAliasForm
    page_title = _('Add Paper Identifier')

    def get_initial(self):
        qs = models.Paper.objects.select_related('posted_by')
        paper = get_object_or_404(qs, pk=self.kwargs['pk'])
        if not paper.is_owned_by(self.request.user):
            raise PermissionDenied(_('You are not one of the authors.'))
        self.parent = paper
        ret = super(LinkPaperAliasView, self).get_initial()
        ret['target'] = paper
        return ret

    def form_valid(self, form):
        # Deal with possible INSERT/UPDATE race condition
        try:
            with atomic():
                ret = super(LinkPaperAliasView, self).form_valid(form)
                self.parent.changed_by = self.request.user
                self.parent.save(update_fields=['last_changed', 'changed_by'])
                return ret
        except IntegrityError:
            logger.info('Race condition detected while linking user alias.',
                exc_info=False)
            return self.form_invalid(form)

    def get_success_url(self):
        return self.parent.get_absolute_url()

@method_decorator(login_required, name='dispatch')
class UnlinkPaperAliasView(BaseUnlinkAliasView):
    queryset = models.PaperAlias.objects.select_related('target__posted_by')
    page_title = _('Delete Paper Identifier')

    def get_object(self, *args, **kwargs):
        ret = super(UnlinkPaperAliasView, self).get_object(*args, **kwargs)
        if ret.target is None:
            raise Http404()
        elif not ret.target.is_owned_by(self.request.user):
            raise PermissionDenied(_('You are not one of the authors.'))
        elif not ret.is_deletable():
            raise PermissionDenied(_('This identifier is permanent.'))
        self.target = ret.target
        return ret

    def perform_delete(self):
        super(UnlinkPaperAliasView, self).perform_delete()
        self.object.target.changed_by = self.request.user
        self.object.target.save(update_fields=['last_changed', 'changed_by'])

    def get_success_url(self):
        return self.target.get_absolute_url()

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class AddCitationsFormView(BaseModelFormsetView):
    queryset = models.PaperAlias.objects.none()
    form_class = PaperAliasFormset
    page_title = _('Add Citations')
    extra_forms = 20

    def get_form_kwargs(self):
        logger.info('AddCitationsFormView.get_form_kwargs()')
        qs = models.Paper.objects
        if self.request.method == 'POST':
            qs = qs.select_for_update()
        paper = get_object_or_404(qs, pk=self.kwargs['pk'])
        if not paper.is_owned_by(self.request.user):
            raise PermissionDenied(_('You are not one of the authors.'))
        self.parent = paper
        ret = super(AddCitationsFormView, self).get_form_kwargs()
        ret['allow_sciswarm'] = True
        ret['label'] = _('Biblio entry:')
        return ret

    def form_valid(self, formset):
        logger.info('AddCitationsFormView.form_valid()')
        paper = self.parent
        for form in formset:
            form.instance.paper = paper
        ret = super(AddCitationsFormView, self).form_valid(formset)
        logger.info('object_list: %s' % str(self.object_list))
        clean_list = remove_duplicates(self.object_list, paper.bibliography)
        logger.info('clean_list: %s' % str(clean_list))
        paper.bibliography.add(*clean_list)
        paper.changed_by = self.request.user
        paper.save(update_fields=['last_changed', 'changed_by'])
        return ret

    def get_success_url(self):
        logger.info('AddCitationsFormView.get_success_url()')
        return self.parent.get_absolute_url()

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class DeleteCitationView(BaseDeleteView):
    template_name = 'core/paper/delete_citation.html'

    def get_object(self, *args, **kwargs):
        qs = models.Paper.objects
        if self.request.method == 'POST':
            qs = qs.select_for_update()
        paper = get_object_or_404(qs, pk=self.kwargs['paper'])
        if not paper.is_owned_by(self.request.user):
            raise PermissionDenied(_('You are not one of the authors.'))
        self.parent = paper
        qs = paper.bibliography.select_related('target')
        return get_object_or_404(qs, pk=self.kwargs['ref'])

    def perform_delete(self):
        self.parent.bibliography.remove(self.object)
        self.parent.changed_by = self.request.user
        self.parent.save(update_fields=['last_changed', 'changed_by'])

    def get_success_url(self):
        return self.parent.get_absolute_url()

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class PaperAuthorshipConfirmationView(BaseUpdateView):
    form_class = AuthorshipConfirmationForm
    template_name = 'core/paper/authorship_confirmation.html'

    def get_queryset(self):
        return models.Paper.objects.filter_by_author(self.request.user)

    def get_form_kwargs(self, *args, **kwargs):
        ret = super(PaperAuthorshipConfirmationView, self).get_form_kwargs(
            *args, **kwargs)
        ret['user'] = self.request.user
        return ret

    def get_context_data(self, *args, **kwargs):
        ret = super(PaperAuthorshipConfirmationView, self).get_context_data(
            *args, **kwargs)
        reftab = models.PaperAuthorReference.query_model
        obj = ret['object']
        query = ((reftab.author_alias.target == self.request.user) &
            (reftab.paper == obj))
        qs = models.PaperAuthorReference.objects.filter(query)
        ret['alias_list'] = qs.select_related('author_alias')
        return ret
