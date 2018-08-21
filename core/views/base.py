from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
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

    def get_initial(self):
        return self.initial.copy()

    def get_prefix(self):
        return self.prefix

    def get_form_class(self):
        if self.form_class is None:
            raise ImproperlyConfigured("'form_class' attribute is required.")
        return self.form_class

    def get_form_kwargs(self):
        qs = super(SearchListView, self).get_queryset()
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
            qs = super(SearchListView, self).get_queryset()
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
