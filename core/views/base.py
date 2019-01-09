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
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views import generic
from .utils import PageNavigator

class BaseCreateView(generic.CreateView):
    template_name = 'common/edit.html'
    page_title = _('Create Record')

    def get_context_data(self, **kwargs):
        ret = super(BaseCreateView, self).get_context_data(**kwargs)
        ret.setdefault('page_title', self.page_title)
        return ret

class BaseUpdateView(generic.UpdateView):
    template_name = 'common/edit.html'
    page_title = _('Update Record')

    def get_context_data(self, **kwargs):
        ret = super(BaseUpdateView, self).get_context_data(**kwargs)
        ret.setdefault('page_title', self.page_title)
        return ret

@method_decorator(login_required, name='dispatch')
class RestrictedUpdateView(BaseUpdateView):
    def get_object(self, queryset=None):
        ret = super(RestrictedUpdateView, self).get_object(queryset)
        if not ret.is_own(self.request):
            msg = _('You do not have permission to edit this record.')
            raise AccessDenied(msg)
        return ret

class BaseListView(generic.ListView):
    paginate_by = 50

    def paginate_queryset(self, queryset, page_size):
        pagenav = PageNavigator(self.request, queryset, page_size)
        page = pagenav.page
        return (pagenav, page, page.object_list, page.has_other_pages())

class SearchListView(BaseListView):
    initial = {}
    form_class = None
    prefix = None

    def get_base_queryset(self):
        return super(SearchListView, self).get_queryset()

    def get_initial(self):
        return self.initial.copy()

    def get_prefix(self):
        return self.prefix

    def get_form_class(self):
        if self.form_class is None:
            raise ImproperlyConfigured("'form_class' attribute is required.")
        return self.form_class

    def get_form_kwargs(self):
        qs = self.get_base_queryset()
        kwargs = dict(initial=self.get_initial(), prefix=self.get_prefix(),
            data=self.request.GET or None, queryset=qs)
        return kwargs

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        return form_class(**self.get_form_kwargs())

    def get_queryset(self):
        qs = None
        if self.form.is_valid():
            qs = self.form.queryset
        if qs is None:
            qs = self.get_base_queryset()
        return qs

    def get(self, *args, **kwargs):
        self.form = self.get_form()
        if self.form.is_valid():
            return self.form_valid(self.form)
        else:
            return self.form_invalid(self.form)

    def form_valid(self, form):
        return super(SearchListView, self).get(self.request, *self.args,
            **self.kwargs)

    def form_invalid(self, form):
        return super(SearchListView, self).get(self.request, *self.args,
            **self.kwargs)

    def get_context_data(self, *args, **kwargs):
        ret = super(SearchListView, self).get_context_data(*args, **kwargs)
        ret['form'] = self.form
        return ret

class BaseModelFormsetView(generic.FormView):
    model = None
    queryset = None
    template_name = 'common/formset.html'
    page_title = None
    extra_forms = None

    def get_queryset(self):
        if self.queryset is not None:
            return self.queryset.all()
        elif self.model is not None:
            return self.model._default_manager.all()
        msg = '%(cls)s is missing a queryset. Define %(cls)s.model, %(cls)s.queryset or override %(cls)s.get_queryset().'
        raise ImproperlyConfigured(msg % {'cls': self.__class__.__name__})

    def get_form_kwargs(self):
        return dict()

    def get_formset_kwargs(self):
        kwargs = {
            'queryset': self.get_queryset(),
            'form_kwargs': self.get_form_kwargs(),
            'initial': self.get_initial(),
            'prefix': self.get_prefix()
        }

        if self.request.method in ('POST', 'PUT'):
            kwargs.update({
                'data': self.request.POST,
                'files': self.request.FILES,
            })
        return kwargs

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        form = form_class(**self.get_formset_kwargs())
        if self.extra_forms is not None:
            form.extra = self.extra_forms
        return form

    def form_valid(self, form):
        self.object_list = form.save()
        return super(BaseModelFormsetView, self).form_valid(form)

    def get_context_data(self, *args, **kwargs):
        ret = super(BaseModelFormsetView,self).get_context_data(*args,**kwargs)
        if self.page_title is not None:
            ret['page_title'] = self.page_title
        return ret

    def get(self, *args, **kwargs):
        self.object_list = None
        return super(BaseModelFormsetView, self).get(*args, **kwargs)

    def post(self, *args, **kwargs):
        self.object_list = None
        return super(BaseModelFormsetView, self).post(*args, **kwargs)

class BaseDeleteView(generic.DeleteView):
    page_title = None

    def perform_delete(self):
        self.object.delete()

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.perform_delete()
        return HttpResponseRedirect(success_url)

    def get_context_data(self, *args, **kwargs):
        ret = super(BaseDeleteView, self).get_context_data(*args,**kwargs)
        if self.page_title is not None:
            ret['page_title'] = self.page_title
        return ret

class BaseUnlinkAliasView(BaseDeleteView):
    template_name = 'common/unlink_alias.html'

    def perform_delete(self):
        self.object.unlink()
