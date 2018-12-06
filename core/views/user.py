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
from django.db.transaction import atomic
from django.http import Http404
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView, FormView
from .base import BaseCreateView, BaseUnlinkAliasView
from .utils import PageNavigator
from ..utils.html import NavigationBar
from ..utils.utils import logger
from ..forms.user import UserAliasForm, MassAuthorshipConfirmationForm
from .. import models

class UserDetailView(DetailView):
    queryset = models.User.objects.filter_active()
    template_name = 'core/user/user_detail.html'
    slug_url_kwarg = 'username'
    slug_field = 'username'

    def get_context_data(self, *args, **kwargs):
        ret = super(UserDetailView, self).get_context_data(*args, **kwargs)
        obj = ret['object']
        # Security precaution
        obj.password = ''
        ret['alias_list'] = obj.useralias_set.select_related('target')
        links = [
            (_('Posted papers'), 'core:user_posted_paper_list', tuple(),
                dict(username=obj.username)),
            (_('Authored papers'), 'core:user_authored_paper_list', tuple(),
                dict(username=obj.username)),
        ]
        ret['navbar'] = NavigationBar(self.request, links)
        # TODO: Show latest events from this user
        return ret

@method_decorator(login_required, name='dispatch')
class LinkUserAliasView(BaseCreateView):
    form_class = UserAliasForm
    page_title = _('Add Personal Identifier')

    def get_initial(self):
        ret = super(LinkUserAliasView, self).get_initial()
        ret['target'] = self.request.user
        return ret

    def form_valid(self, form):
        # Deal with possible INSERT/UPDATE race condition
        try:
            with atomic():
                return super(LinkUserAliasView, self).form_valid(form)
        except IntegrityError:
            logger.info('Race condition detected while linking user alias.',
                exc_info=False)
            return self.form_invalid(form)

    def get_success_url(self):
        kwargs = dict(username=self.request.user.username)
        return reverse('core:user_detail', kwargs=kwargs)

@method_decorator(login_required, name='dispatch')
class UnlinkUserAliasView(BaseUnlinkAliasView):
    queryset = models.UserAlias.objects.select_related('target')
    page_title = _('Delete Personal Identifier')

    def get_object(self, *args, **kwargs):
        ret = super(UnlinkUserAliasView, self).get_object(*args, **kwargs)
        if ret.target != self.request.user:
            raise Http404()
        elif not ret.is_deletable():
            raise PermissionDenied(_('This identifier is permanent.'))
        return ret

    def get_success_url(self):
        kwargs = dict(username=self.request.user.username)
        return reverse('core:user_detail', kwargs=kwargs)

@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class MassAuthorshipConfirmationView(FormView):
    form_class = MassAuthorshipConfirmationForm
    template_name = 'core/user/mass_authorship_confirmation.html'
    success_url = reverse_lazy('core:mass_authorship_confirmation')

    def get_form_kwargs(self, *args, **kwargs):
        ret = super(MassAuthorshipConfirmationView,self).get_form_kwargs(*args,
            **kwargs)
        reftab = models.Paper.query_model.paperauthorreference
        query = (reftab.confirmed.isnull() &
            (reftab.author_alias.target==self.request.user))
        qs = models.Paper.objects.filter(query).distinct().order_by('pk')
        pagenav = PageNavigator(self.request, qs, 50)
        page = pagenav.page
        self.paginator = pagenav
        self.object_list = page.object_list
        ret['paper_list'] = page.object_list
        ret['user'] = self.request.user
        return ret

    def form_valid(self, form):
        form.save()
        return super(MassAuthorshipConfirmationView, self).form_valid(form)

    def get_context_data(self, *args, **kwargs):
        ret = super(MassAuthorshipConfirmationView, self).get_context_data(
            *args, **kwargs)
        ret['paginator'] = self.paginator
        ret['object_list'] = self.object_list
        links = [(_('Rejected papers'), 'core:rejected_authorship_paper_list',
            tuple(), dict())]
        ret['navbar'] = NavigationBar(self.request, links)
        return ret
