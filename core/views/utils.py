from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME, views as auth
from django.core import paginator
from django.utils.encoding import force_text
from django.http import Http404
from django.shortcuts import render
from django.utils.html import format_html, mark_safe
from django.utils.http import urlencode
from django.utils.translation import pgettext, ugettext as _
from ..utils.html import NavigationBar

def error_page(request, status, message, title=None):
    template = 'core/utils/error.html'
    resolver = request.resolver_match
    if not title:
        title = _('Error {0}').format(status)
    context = dict(page_title=title, message=message)
    return render(request, template, context, status=status)

def bad_request(request, exception=None):
    if isinstance(exception, Exception):
        exception = force_text(exception)
    if not exception:
        exception = _('Invalid request')
    return error_page(request, 400, exception)

def permission_denied(request, exception=None):
    title = _('Permission denied')
    if isinstance(exception, Exception):
        exception = force_text(exception)
    if not exception:
        exception = _('You do not have permission to access this page.')
    return error_page(request, 403, exception, title)

def not_found(request, exception=None):
    message = _('The requested page does not exist.')
    return error_page(request, 404, message)

def method_not_allowed(request, exception=None):
    if isinstance(exception, Exception):
        exception = force_text(exception)
    if not exception:
        exception = _('Accessing this page using the {0} method is not allowed.')
        exception = exception.format(request.method)
    return error_page(request, 405, exception)

def internal_error(request, exception=None):
    if isinstance(exception, Exception):
        exception = force_text(exception)
    if not exception:
        exception = _('Unexpected error occurred while processing your request. We will fix the problem soon.')
    return error_page(request, 500, exception)

def editing_forbidden_error(request, message=None):
    title = _('Cannot Edit Record')
    if not message:
        message = _('You cannot edit this record.')
    return error_page(request, 403, message, title)

def redirect_to_login(next, login_url=None, redirect_field_name=None):
    if not redirect_field_name:
        redirect_field_name = settings.SYSTEM_GET_FIELDS.get('login_next',
            REDIRECT_FIELD_NAME)
    return auth.redirect_to_login(next, login_url=login_url,
        redirect_field_name=redirect_field_name)

class PageNavigator(object):
    def __init__(self, request, object_list, per_page=25, arg_name=None):
        if not arg_name:
            arg_name = settings.SYSTEM_GET_FIELDS.get('page_number', 'page')
        self.request = request
        self.object_list = object_list
        self.arg_name = arg_name
        self.paginator = paginator.Paginator(object_list, per_page)
        try:
            self.page = self.paginator.page(request.GET.get(arg_name, 1))
        except (paginator.PageNotAnInteger, paginator.EmptyPage):
            raise Http404()

    def __str__(self):
        if not self.page.has_other_pages():
            return ''
        urlargs = self.request.GET.copy()
        tokens = ['<div class="pagenav">']
        linktpl = '<a href="?{url}">{title}</a>'
        if self.page.has_previous():
            urlargs.pop(self.arg_name, None)
            title = pgettext('navigation', 'First')
            kwargs = dict(url=urlencode(urlargs, True), title=title)
            tokens.append(format_html(linktpl, **kwargs))
            tmp = self.page.previous_page_number()
            if tmp > 1:
                urlargs[self.arg_name] = tmp
            title = pgettext('navigation', 'Previous')
            kwargs = dict(url=urlencode(urlargs, True), title=title)
            tokens.append(format_html(linktpl, **kwargs))
        tpl = pgettext('navigation', '%(page)s of %(total)s')
        tmp = dict(page=self.page.number, total=self.paginator.num_pages)
        tokens.append(tpl % tmp)
        if self.page.has_next():
            urlargs[self.arg_name] = self.page.next_page_number()
            title = pgettext('navigation', 'Next')
            kwargs = dict(url=urlencode(urlargs, True), title=title)
            tokens.append(format_html(linktpl, **kwargs))
            urlargs[self.arg_name] = self.paginator.num_pages
            title = pgettext('navigation', 'Last')
            kwargs = dict(url=urlencode(urlargs, True), title=title)
            tokens.append(format_html(linktpl, **kwargs))
        tokens.append('</div>')
        return mark_safe(' '.join(tokens))
