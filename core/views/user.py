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
from django.db.models import aggregates
from django.db.transaction import atomic
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView, FormView
from .base import BaseCreateView, BaseListView, BaseUnlinkAliasView
from .utils import fetch_authors, manage_authorship_navbar, PageNavigator
from ..models import const
from ..utils.html import NavigationBar
from ..utils.utils import logger, fold_or
from ..forms.user import (PersonAliasForm, MassAuthorshipConfirmationForm,
    MassAuthorshipClaimForm, FeedSubscriptionForm,
    PaperManagementDelegationForm)
from .. import models
import unicodedata

class PersonFollowerListView(BaseListView):
    template_name = 'core/person/person_list.html'

    def get_queryset(self):
        ptab = models.Person.query_model
        qs = models.Person.objects.filter_username(self.kwargs['username'])
        self.person = get_object_or_404(qs.filter_active())
        query = (ptab.feedsubscription.poster == self.person)
        order = aggregates.Min(ptab.feedsubscription.pk.f())
        qs = models.Person.objects.filter_active().filter(query).distinct()
        return qs.annotate(order=order).order_by('order')

    def get_context_data(self, *args, **kwargs):
        ret = super(PersonFollowerListView, self).get_context_data(*args,
            **kwargs)
        ret['page_title'] = _('Followers of %s') % self.person.full_name
        ret['navbar'] = ''
        return ret

class PersonSubscriptionListView(BaseListView):
    template_name = 'core/person/person_list.html'

    def get_queryset(self):
        ptab = models.Person.query_model
        qs = models.Person.objects.filter_username(self.kwargs['username'])
        self.person = get_object_or_404(qs.filter_active())
        query = (ptab.follower.follower == self.person)
        order = aggregates.Min(ptab.follower.pk.f())
        qs = models.Person.objects.filter_active().filter(query).distinct()
        return qs.annotate(order=order).order_by('order')

    def get_context_data(self, *args, **kwargs):
        ret = super(PersonSubscriptionListView, self).get_context_data(*args,
            **kwargs)
        ret['page_title'] = _('People Followed by %s') % self.person.full_name
        ret['navbar'] = ''
        return ret

class PersonDetailView(DetailView):
    queryset = models.Person.objects.filter_active()
    template_name = 'core/person/person_detail.html'

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        queryset = queryset.filter_username(self.kwargs['username'])
        return get_object_or_404(queryset)

    def get_context_data(self, *args, **kwargs):
        ret = super(PersonDetailView, self).get_context_data(*args, **kwargs)
        obj = ret['object']
        ret['alias_list'] = obj.personalias_set.select_related('target')
        for item in ret['alias_list']:
            item.is_deletable()
        links = [
            (_('Feed'), 'core:person_event_feed', tuple(),
                dict(username=self.kwargs['username'])),
            (_('Following'), 'core:person_subscription_list', tuple(),
                dict(username=self.kwargs['username'])),
            (_('Followers'), 'core:person_follower_list', tuple(),
                dict(username=self.kwargs['username'])),
            (_('Posted papers'), 'core:person_posted_paper_list', tuple(),
                dict(username=self.kwargs['username'])),
            (_('Authored papers'), 'core:person_authored_paper_list', tuple(),
                dict(username=self.kwargs['username'])),
            (_('Recommended papers'), 'core:person_recommended_paper_list',
                tuple(), dict(username=self.kwargs['username'])),
        ]
        ret['edit_access'] = False
        ret['subscribe_form'] = None
        ret['delegated_permissions'] = False
        if self.request.user.is_authenticated:
            ret['edit_access'] = (self.request.user.person == obj)
            if self.request.user.person == obj:
                links.append((_('Edit profile'), 'core:edit_profile', tuple(),
                    dict()))
            else:
                links.append((_('Delegate paper management'),
                    'core:delegate_paper_management', tuple(),
                    dict(username=obj.username)))
                query = (models.Person.query_model.pk == obj.pk)
                qs = self.request.user.person.paper_managers.filter(query)
                ret['delegated_permissions'] = qs.exists()
                ret['subscribe_form'] = FeedSubscriptionForm(poster=obj,
                    follower=self.request.user.person)
        ret['navbar'] = NavigationBar(self.request, links)
        # TODO: Show latest events from this user
        return ret

@method_decorator(login_required, name='dispatch')
class LinkPersonAliasView(BaseCreateView):
    form_class = PersonAliasForm
    page_title = _('Add Personal Identifier')

    def get_initial(self):
        ret = super(LinkPersonAliasView, self).get_initial()
        ret['target'] = self.request.user.person
        return ret

    def form_valid(self, form):
        # Deal with possible INSERT/UPDATE race condition
        try:
            with atomic():
                return super(LinkPersonAliasView, self).form_valid(form)
        except IntegrityError:
            logger.info('Race condition detected while linking user alias.',
                exc_info=False)
            return self.form_invalid(form)

    def get_success_url(self):
        kwargs = dict(username=self.request.user.username)
        return reverse('core:person_detail', kwargs=kwargs)

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class UnlinkPersonAliasView(BaseUnlinkAliasView):
    queryset = models.PersonAlias.objects.select_related('target')
    page_title = _('Delete Personal Identifier')

    def get_object(self, *args, **kwargs):
        ret = super(UnlinkPersonAliasView, self).get_object(*args, **kwargs)
        if ret.target != self.request.user.person:
            raise Http404()
        elif not ret.is_deletable():
            raise PermissionDenied(_('This identifier is permanent.'))
        return ret

    def perform_delete(self):
        person = self.object.target
        # Lock papers referencing this alias
        papertab = models.Paper.query_model
        partab = papertab.paperauthorreference
        evtab = models.FeedEvent.query_model
        query = ((partab.author_alias == self.object) &
            (partab.confirmed == True))
        bool(models.Paper.objects.filter(query).select_for_update())

        # Unlink alias
        super(UnlinkPersonAliasView, self).perform_delete()
        self.object.paperauthorreference_set.update(confirmed=None)

        # Delete obsolete authorship confirmation events
        evtype = const.user_feed_events.AUTHORSHIP_CONFIRMED
        subq = models.Paper.objects.filter_by_author(person, True)
        subq = subq.values_list('pk')
        query = ((partab.author_alias == self.object) &
            ~papertab.pk.belongs(subq))
        paper_qs = models.Paper.objects.filter(query)
        query = ((evtab.person == person) & evtab.paper.belongs(paper_qs) &
            (evtab.event_type == evtype))
        models.FeedEvent.objects.filter(query).delete()

    def get_success_url(self):
        kwargs = dict(username=self.request.user.username)
        return reverse('core:person_detail', kwargs=kwargs)

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class MassAuthorshipConfirmationView(FormView):
    form_class = MassAuthorshipConfirmationForm
    template_name = 'core/person/mass_authorship_confirmation.html'
    success_url = reverse_lazy('core:mass_authorship_confirmation')

    def get_form_kwargs(self, *args, **kwargs):
        ret = super(MassAuthorshipConfirmationView,self).get_form_kwargs(*args,
            **kwargs)
        papertab = models.Paper.query_model
        reftab = papertab.paperauthorreference
        person = self.request.user.person
        query = (models.PaperReview.query_model.deleted == False)
        subqs = models.PaperReview.objects.filter_by_author(person)
        subqs = subqs.filter(query).values_list('paper_id')
        query = (~papertab.pk.belongs(subqs) & reftab.confirmed.isnull() &
            (reftab.author_alias.target == person))
        qs = models.Paper.objects.filter_public().filter(query).distinct()
        qs = qs.order_by('pk')
        pagenav = PageNavigator(self.request, qs, 50)
        page = pagenav.page
        self.paginator = pagenav
        self.object_list = page.object_list
        ret['paper_list'] = page.object_list
        ret['person'] = self.request.user.person
        return ret

    def form_valid(self, form):
        form.save()
        return super(MassAuthorshipConfirmationView, self).form_valid(form)

    def get_context_data(self, *args, **kwargs):
        ret = super(MassAuthorshipConfirmationView, self).get_context_data(
            *args, **kwargs)
        ret['paginator'] = self.paginator
        paper_list = fetch_authors(self.object_list)
        field_map = dict((p.pk, f) for p,f in ret['form'].paper_fields)
        ret['object_list'] = [(p,a,n,field_map[p.pk]) for p,a,n in paper_list]
        ret['navbar'] = manage_authorship_navbar(self.request)
        ret['page_title'] = _('Confirm Authorship')
        return ret

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class MassAuthorshipClaimView(FormView):
    form_class = MassAuthorshipClaimForm
    template_name = 'core/person/mass_authorship_confirmation.html'
    success_url = reverse_lazy('core:mass_claim_authorship')

    def get_form_kwargs(self, *args, **kwargs):
        ret = super(MassAuthorshipClaimView, self).get_form_kwargs(*args,
            **kwargs)
        # Prepare name variants to search for
        person = self.request.user.person
        last_name = person.last_name.strip()
        first_name = person.first_name.split()
        search_names = set()
        if first_name:
            first_name = first_name[0]
            search_names.add(last_name + ' ' + first_name)
            search_names.add(last_name + ' ' + first_name[:1])
        else:
            search_names.add(last_name)
        tmp = [x.casefold() for x in search_names]
        search_names.update(tmp)
        tmp = [unicodedata.normalize('NFKD', x).encode('ascii',
            'ignore').decode('ascii') for x in search_names]
        search_names.update((x for x in tmp if x))

        # Search query
        papertab = models.Paper.query_model
        nametab = papertab.paperauthorname
        reftab = models.PaperAuthorReference.query_model
        query = (models.PaperReview.query_model.deleted == False)
        subqs = models.PaperReview.objects.filter_by_author(person)
        subqs = subqs.filter(query).values_list('paper_id')

        query = (reftab.author_alias.target == person)
        subqs2 = models.PaperAuthorReference.objects.filter(query)
        subqs2 = subqs2.values_list('paper_id')

        query = (~papertab.pk.belongs(subqs) & ~papertab.pk.belongs(subqs2) &
            fold_or([nametab.author_name.tsphrase(x) for x in search_names]))
        qs = models.Paper.objects.filter_public().filter(query).distinct()
        qs = qs.order_by('pk')
        pagenav = PageNavigator(self.request, qs, 50)
        page = pagenav.page
        self.paginator = pagenav
        self.object_list = page.object_list
        ret['paper_list'] = page.object_list
        ret['person'] = self.request.user.person
        return ret

    def form_valid(self, form):
        form.save()
        return super(MassAuthorshipClaimView, self).form_valid(form)

    def get_context_data(self, *args, **kwargs):
        ret = super(MassAuthorshipClaimView, self).get_context_data(*args,
            **kwargs)
        ret['paginator'] = self.paginator
        paper_list = fetch_authors(self.object_list)
        field_map = dict((p.pk, f) for p,f in ret['form'].paper_fields)
        ret['object_list'] = [(p,a,n,field_map[p.pk]) for p,a,n in paper_list]
        ret['navbar'] = manage_authorship_navbar(self.request)
        ret['page_title'] = _('Claim Authorship')
        return ret

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class FeedSubscriptionFormView(FormView):
    form_class = FeedSubscriptionForm

    def get_form_kwargs(self, *args, **kwargs):
        ret = super(FeedSubscriptionFormView, self).get_form_kwargs(*args,
            **kwargs)
        ret['follower'] = self.request.user.person
        qs = models.Person.objects.filter_username(self.kwargs['username'])
        self.person = get_object_or_404(qs.filter_active())
        ret['poster'] = self.person
        return ret

    def get(self, *args, **kwargs):
        return redirect('core:person_detail', username=self.kwargs['username'])

    def form_valid(self, form):
        form.save()
        return redirect(self.person.get_absolute_url())

@method_decorator(login_required, name='dispatch')
class PaperManagersListView(BaseListView):
    template_name = 'core/person/paper_managers_list.html'

    def get_queryset(self):
        # List inactive users, too
        return self.request.user.person.paper_managers.all()

    def get_context_data(self, *args, **kwargs):
        ret = super(PaperManagersListView, self).get_context_data(*args,
            **kwargs)
        links = [(_('Delegating authors'), 'core:user_delegating_authors_list',
            tuple(), dict())]
        ret['navbar'] = NavigationBar(self.request, links)
        ret['page_title'] = _('Your Delegated Paper Managers')
        return ret

@method_decorator(login_required, name='dispatch')
class DelegatingAuthorsListView(BaseListView):
    template_name = 'core/person/person_list.html'

    def get_queryset(self):
        return self.request.user.person.delegating_authors.filter_active()

    def get_context_data(self, *args, **kwargs):
        ret = super(DelegatingAuthorsListView, self).get_context_data(*args,
            **kwargs)
        links = [(_('Your paper managers'), 'core:user_paper_managers_list',
            tuple(), dict())]
        ret['navbar'] = NavigationBar(self.request, links)
        ret['page_title'] = _('Authors Who Delegated Paper Management to You')
        return ret

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class PaperManagementDelegationView(FormView):
    form_class = PaperManagementDelegationForm
    template_name = 'core/person/delegate_paper_management.html'

    def get_form_kwargs(self, *args, **kwargs):
        ret = super(PaperManagementDelegationView, self).get_form_kwargs(*args,
            **kwargs)
        ret['author'] = self.request.user.person
        # Allow (un)delegation even for inactive users
        qs = models.Person.objects.filter_username(self.kwargs['username'])
        self.person = get_object_or_404(qs)
        if self.person == self.request.user.person:
            raise Http404()
        ret['target'] = self.person
        return ret

    def form_valid(self, form):
        form.save()
        return redirect(self.person.get_absolute_url())

    def get_context_data(self, *args, **kwargs):
        ret = super(PaperManagementDelegationView, self).get_context_data(
            *args, **kwargs)
        ret['object'] = self.person
        return ret
