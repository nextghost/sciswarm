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
from django.db import IntegrityError
from django.db.models import prefetch_related_objects
from django.db.transaction import atomic
from django.forms import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView, FormView
from .base import (BaseCreateView, BaseUpdateView, BaseListView,
    SearchListView, BaseModelFormsetView, BaseDeleteView, BaseUnlinkAliasView)
from .utils import (fetch_authors, person_navbar, paper_navbar,
    manage_authorship_navbar)
from ..forms.paper import (PaperSearchForm, PaperForm, PaperAliasForm,
    PaperAliasFormset, PaperAuthorNameFormset, PaperSupplementalLinkForm,
    PaperRecommendationForm, ScienceSubfieldForm, DoiInputForm)
from ..forms.user import (PaperAuthorForm, PersonAliasForm, PersonAliasFormset,
    AuthorshipConfirmationForm)
from ..models import const
from ..utils.crossref import crossref_fetch, crossref_import_bridge
from ..utils.html import NavigationBar
from ..utils.paper import paper_review_rating_subquery, bibcoupling_subquery
from ..utils.utils import list_map, logger, remove_duplicates, fold_or
from .. import models

class BasePaperListView(SearchListView):
    queryset = models.Paper.objects.filter_public()
    form_class = PaperSearchForm
    template_name = 'core/paper/paper_list.html'
    page_title = _('Latest papers')

    def get_queryset(self):
        qs = None
        if self.form.is_valid():
            # Workaround for PostgreSQL query optimizer bug
            qs = self.form.queryset
            if self.form.filter:
                ordering = self.get_ordering()
                if ordering is None:
                    ordering = models.Paper._meta.ordering
                if isinstance(ordering, (list, tuple)):
                    ordering = list(ordering)
                else:
                    ordering = [ordering]
                ordering.append('public')
                qs = qs.order_by(*ordering)
        if qs is None:
            qs = self.get_base_queryset()
        return qs

    def get_context_data(self, *args, **kwargs):
        ret = super(BasePaperListView, self).get_context_data(*args, **kwargs)
        ret['object_list'] = fetch_authors(ret['object_list'])
        ret['page_title'] = self.page_title
        ret['navbar'] = ''
        return ret

class PaperListView(BasePaperListView):
    ordering = ('-date_posted',)

class CitedByPaperListView(BasePaperListView):
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
        ret['navbar'] = paper_navbar(self.request, self.paper)
        return ret

class PersonPostedPaperListView(BasePaperListView):
    def get_base_queryset(self):
        qs = models.Person.objects.filter_active()
        qs = qs.filter_username(self.kwargs['username'])
        self.person = get_object_or_404(qs)
        return self.person.posted_paper_set.filter_public()

    def get_context_data(self, *args, **kwargs):
        ret = super(PersonPostedPaperListView, self).get_context_data(*args,
            **kwargs)
        ret['page_title'] = _('Papers Posted by %s') % self.person.full_name
        ret['navbar'] = person_navbar(self.request, self.kwargs['username'],
            self.person)
        return ret

class PersonAuthoredPaperListView(BasePaperListView):
    def get_base_queryset(self):
        qs = models.Person.objects.filter_active()
        qs = qs.filter_username(self.kwargs['username'])
        self.person = get_object_or_404(qs)
        reftab = models.Paper.query_model.paperauthorreference
        # Show only confirmed papers
        query = ((reftab.author_alias.target == self.person) &
            (reftab.confirmed == True))
        return models.Paper.objects.filter_public().filter(query).distinct()

    def get_context_data(self, *args, **kwargs):
        ret = super(PersonAuthoredPaperListView, self).get_context_data(*args,
            **kwargs)
        ret['page_title'] = _('Papers by %s') % self.person.full_name
        ret['navbar'] = person_navbar(self.request, self.kwargs['username'],
            self.person)
        return ret

class PersonRecommendedPaperListView(BasePaperListView):
    def get_base_queryset(self):
        qs = models.Person.objects.filter_active()
        qs = qs.filter_username(self.kwargs['username'])
        self.person = get_object_or_404(qs)
        evtab = models.Paper.query_model.feedevent
        query = ((evtab.person == self.person) &
            (evtab.event_type == const.user_feed_events.PAPER_RECOMMENDATION))
        return models.Paper.objects.filter_public().filter(query)

    def get_context_data(self, *args, **kwargs):
        ret = super(PersonRecommendedPaperListView, self).get_context_data(
            *args, **kwargs)
        title = _('Papers Recommended by %s') % self.person.full_name
        ret['page_title'] = title
        ret['navbar'] = person_navbar(self.request, self.kwargs['username'],
            self.person)
        return ret

@method_decorator(login_required, name='dispatch')
class RejectedAuthorshipPaperListView(BasePaperListView):
    page_title = _('Papers You Have Rejected')

    def get_base_queryset(self):
        reftab = models.Paper.query_model.paperauthorreference
        query = ((reftab.author_alias.target.pk==self.request.user.person_id) &
            (reftab.confirmed == False))
        return models.Paper.objects.filter_public().filter(query).distinct()

    def get_context_data(self, *args, **kwargs):
        ret = super(RejectedAuthorshipPaperListView, self).get_context_data(
            *args, **kwargs)
        ret['navbar'] = manage_authorship_navbar(self.request)
        return ret

class SimilarPaperListView(BaseListView):
    template_name = 'core/paper/similar_paper_list.html'

    def get_queryset(self):
        qs = models.Paper.objects.filter_public()
        self.paper = get_object_or_404(qs, pk=self.kwargs['pk'])
        alias_list = self.paper.bibliography.values_list('pk')
        return bibcoupling_subquery(alias_list, [self.paper.pk])

    def get_context_data(self, *args, **kwargs):
        ret = super(SimilarPaperListView, self).get_context_data(*args,
            **kwargs)
        id_list = [(x['paper_id'], x['weight']) for x in ret['object_list']]
        paper_map = models.Paper.objects.in_bulk([pk for pk,w in id_list])
        paper_list = []
        for pk, weight in id_list:
            paper = paper_map[pk]
            paper.weight = weight
            paper_list.append(paper)
        ret['object_list'] = fetch_authors(paper_list)
        ret['navbar'] = paper_navbar(self.request, self.paper)
        ret['page_title'] = _('Papers Similar to %s') % self.paper.name
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
        papertab = models.Paper.query_model
        qs = models.PaperAuthorReference.objects.filter_unrejected(obj)
        ret['author_list'] = qs.select_related('author_alias__target')
        ret['author_names'] = obj.paperauthorname_set.all()
        ret['bibliography'] = obj.bibliography.all()
        ret['keyword_list'] = obj.paperkeyword_set.all()
        ret['alias_list'] = obj.paperalias_set.all()
        ret['suplink_list'] = obj.papersupplementallink_set.all()
        ret['field_list'] = obj.fields.all()
        query = (papertab.bibliography.target == obj)
        cite_count = models.Paper.objects.filter_public().filter(query).count()
        ret['citation_count'] = cite_count
        result = paper_review_rating_subquery(obj.pk).execute()
        ret['global_rating'] = result.first()
        ret['network_rating'] = None
        ret['edit_access'] = obj.is_owned_by(self.request.user)
        if self.request.user.is_authenticated:
            person = self.request.user.person
            result = paper_review_rating_subquery(obj.pk, person.pk).execute()
            ret['network_rating'] = result.first()
            ret['recommend_form'] = PaperRecommendationForm(paper=obj,
                person=person)
        ret['navbar'] = paper_navbar(self.request, obj)
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
        subforms['subfield'] = ScienceSubfieldForm(data, prefix='subfield')
        subforms['authors'] = PersonAliasFormset(data, prefix='authors',
            queryset=models.PersonAlias.objects.none(),
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
        try:
            with atomic():
                if all((x.is_valid() for x in formlist)):
                    return self.form_valid(form)
        except IntegrityError:
            logger.info('Race condition detected while linking paper alias.',
                exc_info=False)
        return self.form_invalid(form)

    def form_valid(self, form):
        form.instance.posted_by = self.request.user.person
        form.instance.changed_by = self.request.user.person
        ret = super(CreatePaperView, self).form_valid(form)
        subfield = self.subforms['subfield'].save()
        self.object.fields.add(subfield)
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
        form.instance.changed_by = self.request.user.person
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
        self.parent.changed_by = self.request.user.person
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
        obj = self.object
        obj.paper.changed_by = self.request.user.person
        obj.paper.save(update_fields=['last_changed', 'changed_by'])

        # Delete obsolete authorship confirmation events
        if obj.author_alias.target is not None:
            partab = models.PaperAuthorReference.query_model
            query = ((partab.author_alias.target == obj.author_alias.target) &
                (partab.confirmed == True))
            qs = obj.paper.paperauthorreference_set.filter(query)
            if not qs.exists():
                evtab = models.FeedEvent.query_model
                evtype = const.user_feed_events.AUTHORSHIP_CONFIRMED
                query = ((evtab.person == obj.author_alias.target) &
                    (evtab.paper == obj.paper) & (evtab.event_type == evtype))
                models.FeedEvent.objects.filter(query).delete()

    def get_success_url(self):
        return self.object.paper.get_absolute_url()

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
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
        self.object.paper.changed_by = self.request.user.person
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
                self.parent.changed_by = self.request.user.person
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
        self.object.target.changed_by = self.request.user.person
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
        paper = self.parent
        for form in formset:
            form.instance.paper = paper
        ret = super(AddCitationsFormView, self).form_valid(formset)
        clean_list = remove_duplicates(self.object_list, paper.bibliography)
        paper.bibliography.add(*clean_list)
        paper.changed_by = self.request.user.person
        paper.save(update_fields=['last_changed', 'changed_by'])
        return ret

    def get_success_url(self):
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
        self.parent.changed_by = self.request.user.person
        self.parent.save(update_fields=['last_changed', 'changed_by'])

    def get_success_url(self):
        return self.parent.get_absolute_url()

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class PaperAuthorshipConfirmationView(BaseUpdateView):
    form_class = AuthorshipConfirmationForm
    template_name = 'core/paper/authorship_confirmation.html'

    def get_queryset(self):
        return models.Paper.objects.filter_by_author(self.request.user.person)

    def get_form_kwargs(self, *args, **kwargs):
        ret = super(PaperAuthorshipConfirmationView, self).get_form_kwargs(
            *args, **kwargs)
        ret['person'] = self.request.user.person
        return ret

    def get_context_data(self, *args, **kwargs):
        ret = super(PaperAuthorshipConfirmationView, self).get_context_data(
            *args, **kwargs)
        reftab = models.PaperAuthorReference.query_model
        obj = ret['object']
        query = ((reftab.author_alias.target == self.request.user.person) &
            (reftab.paper == obj))
        qs = models.PaperAuthorReference.objects.filter(query)
        ret['alias_list'] = qs.select_related('author_alias')
        return ret

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class AddSupplementalLinkFormView(BaseCreateView):
    form_class = PaperSupplementalLinkForm
    page_title = _('Add Supplemental Link')

    def get_initial(self):
        paper = get_object_or_404(models.Paper.objects, pk=self.kwargs['pk'])
        if not paper.is_owned_by(self.request.user):
            raise PermissionDenied(_('You are not one of the authors.'))
        self.parent = paper
        ret = super(AddSupplementalLinkFormView, self).get_initial()
        ret['paper'] = paper
        return ret

    def form_valid(self, form):
        ret = super(AddSupplementalLinkFormView, self).form_valid(form)
        self.parent.changed_by = self.request.user.person
        self.parent.save(update_fields=['last_changed', 'changed_by'])
        return ret

    def get_success_url(self):
        return self.parent.get_absolute_url()

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class DeleteSupplementalLinkView(BaseDeleteView):
    queryset = models.PaperSupplementalLink.objects.select_related('paper')
    template_name = 'core/paper/delete_paper_supplemental_link.html'

    def get_object(self, *args, **kwargs):
        qs = self.get_queryset()
        if self.request.method == 'POST':
            qs = qs.select_for_update()
        ret = get_object_or_404(qs, pk=self.kwargs['pk'])
        if not ret.paper.is_owned_by(self.request.user):
            raise PermissionDenied(_('You are not one of the authors.'))
        return ret

    def perform_delete(self):
        super(DeleteSupplementalLinkView, self).perform_delete()
        paper = self.object.paper
        paper.changed_by = self.request.user.person
        paper.save(update_fields=['last_changed', 'changed_by'])

    def get_success_url(self):
        return self.object.paper.get_absolute_url()

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class RecommendPaperFormView(FormView):
    form_class = PaperRecommendationForm

    def get_form_kwargs(self, *args, **kwargs):
        ret = super(RecommendPaperFormView, self).get_form_kwargs(*args,
            **kwargs)
        ret['person'] = self.request.user.person
        qs = models.Paper.objects.filter_public()
        self.paper = get_object_or_404(qs, pk=self.kwargs['pk'])
        ret['paper'] = self.paper
        return ret

    def get(self, *args, **kwargs):
        return redirect('core:paper_detail', pk=self.kwargs['pk'])

    def form_valid(self, form):
        form.save()
        return redirect(self.paper.get_absolute_url())

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class AddScienceSubfieldView(BaseCreateView):
    form_class = ScienceSubfieldForm
    template_name = 'core/paper/science_subfield_form.html'
    page_title = _('Add Scientific Field')

    def get_form_kwargs(self, *args, **kwargs):
        ret = super(AddScienceSubfieldView, self).get_form_kwargs(*args,
            **kwargs)
        qs = models.Paper.objects.filter_public()
        self.parent = get_object_or_404(qs, pk=self.kwargs['pk'])
        if not self.parent.is_owned_by(self.request.user):
            raise PermissionDenied(_('You are not one of the authors.'))
        ret['paper'] = self.parent
        return ret

    def form_valid(self, form):
        self.parent.changed_by = self.request.user.person
        return super(AddScienceSubfieldView, self).form_valid(form)

    def get_success_url(self):
        return self.parent.get_absolute_url()

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class DeleteScienceSubfieldView(BaseDeleteView):
    template_name = 'core/paper/delete_science_subfield.html'

    def get_object(self, *args, **kwargs):
        qs = models.Paper.objects
        if self.request.method == 'POST':
            qs = qs.select_for_update()
        paper = get_object_or_404(qs, pk=self.kwargs['paper'])
        if not paper.is_owned_by(self.request.user):
            raise PermissionDenied(_('You are not one of the authors.'))
        self.parent = paper
        return get_object_or_404(paper.fields, pk=self.kwargs['field'])

    def perform_delete(self):
        self.parent.fields.remove(self.object)
        self.parent.changed_by = self.request.user.person
        self.parent.save(update_fields=['last_changed', 'changed_by'])

    def get_success_url(self):
        return self.parent.get_absolute_url()

class FindSimilarPapersView(FormView):
    form_class = DoiInputForm
    template_name = 'core/paper/find_similar_form.html'

    def _find_paper(self, doi):
        doi_scheme = const.paper_alias_schemes.DOI
        table = models.PaperAlias.query_model
        query = ((table.scheme == doi_scheme) & (table.identifier == doi))
        qs = models.PaperAlias.objects.filter(query).select_related('target')
        alias = qs.first()
        if alias is not None:
            return alias.target
        return None

    def form_valid(self, form):
        doi = form.cleaned_data['doi']
        paper = self._find_paper(doi)

        # Paper found and is public => Redirect to the standard page
        if paper is not None and paper.public:
            return redirect('core:similar_paper_list', pk=paper.pk)

        # If the paper is non-public, request data from Crossref anyway
        try:
            data = crossref_fetch(doi)
        except:
            logger.info('Find similar papers: Crossref query failed. DOI: %s',
                doi, exc_info=True)
            msg = _('Crossref query failed. Please make sure that the DOI is valid and try again later.')
            form.add_error('doi', ValidationError(msg, 'remote'))
            return self.form_invalid(form)

        # Import paper (unless it already exists and is non-public)
        if paper is None and data['name'] is not None:
            bridge = crossref_import_bridge()
            paper_list = bridge.import_papers('', [data], query_crossref=False)
            # The paper may have been created by another process while we were
            # waiting for Crossref response
            if paper_list:
                paper = paper_list[0]
            else:
                paper = self.find_paper(doi)
            if paper is not None and paper.public:
                return redirect('core:similar_paper_list', pk=paper.pk)

        # Paper cannot be imported, generate one-off result page
        paper_list = []
        max_results = 100
        if data['bibliography']:
            table = models.PaperAlias.query_model
            cond_list = [((table.scheme == s) & (table.identifier == i))
                for s,i in data['bibliography']]
            subqs = models.PaperAlias.objects.filter(fold_or(cond_list))
            subqs = subqs.values_list('pk')
            # Limit to 100 best results
            qs = bibcoupling_subquery(subqs)[:max_results+1]
            id_list = [(x['paper_id'], x['weight']) for x in qs]
            paper_map = models.Paper.objects.in_bulk([pk for pk,w in id_list])
            for pk, weight in id_list:
                paper = paper_map[pk]
                paper.weight = weight
                paper_list.append(paper)
        paper_name = data['name'] or doi
        context = dict()
        context['object_list'] = fetch_authors(paper_list[:max_results])
        context['navbar'] = ''
        if len(id_list) > max_results:
            title_tpl = _('Papers Similar to %(name)s (top %(limit)d results)')
            args = dict(name=paper_name, limit=max_results)
            page_title = title_tpl % args
        else:
            page_title = _('Papers Similar to %s') % paper_name
        context['page_title'] = page_title
        template_name = 'core/paper/similar_paper_list.html'
        return render(self.request, template_name, context)

    def get_context_data(self, *args, **kwargs):
        ret = super(FindSimilarPapersView, self).get_context_data(*args,
            **kwargs)
        ret['page_title'] = _('Find Similar Papers')
        return ret
