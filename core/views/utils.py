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

from django.contrib.auth import REDIRECT_FIELD_NAME, views as auth
from django.core import paginator
from django.db.models import QuerySet
from django.utils.encoding import force_text
from django.http import Http404
from django.shortcuts import render
from django.utils.html import format_html, mark_safe
from django.utils.http import urlencode
from django.utils.translation import pgettext, ugettext as _
from ..utils.html import NavigationBar
from ..utils.utils import list_map
from .. import models

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

def paper_navbar(request, paper):
    kwargs = dict(pk=paper.pk)
    links = [
        (_('Paper detail'), 'core:paper_detail', tuple(), kwargs),
        (_('Reviews'), 'core:paperreview_list', tuple(), kwargs),
        (_('Cited by'), 'core:cited_by_paper_list', tuple(), kwargs),
    ]
    if request.user.is_authenticated:
        edit_access = paper.is_owned_by(request.user)
        if edit_access:
            links.append((_('Edit'), 'core:edit_paper', tuple(), kwargs))
        revtab = models.PaperReview.query_model
        query = (revtab.posted_by == request.user.person)
        qs = paper.paperreview_set.filter(query)
        if not (paper.is_author(request.user) or qs.exists()):
            links.append((_('Add review'), 'core:create_paperreview', tuple(),
                kwargs))
        uatab = models.PersonAlias.query_model
        query = (uatab.target.pk == request.user.person_id)
        if paper.authors.filter(query).exists():
            links.append((_('Manage authorship'),
                'core:paper_authorship_confirmation', tuple(), kwargs))
    return NavigationBar(request, links)

def manage_authorship_navbar(request):
    links = [
        (_('Confirm authorship'), 'core:mass_authorship_confirmation', tuple(),
            dict()),
        (_('Claim authorship'), 'core:mass_claim_authorship', tuple(), dict()),
        (_('Rejected papers'), 'core:rejected_authorship_paper_list', tuple(),
            dict())
    ]
    return NavigationBar(request, links)

def fetch_authors(paper_list):
    if isinstance(paper_list, QuerySet):
        paper_list = list(paper_list)
    refs = models.PaperAuthorReference.objects.filter_unrejected(paper_list)
    refs = refs.select_related('author_alias__target')
    ref_map = list_map(((x.paper_id, x) for x in refs))
    antab = models.PaperAuthorName.query_model
    query = antab.paper.belongs(paper_list)
    names = models.PaperAuthorName.objects.filter(query)
    name_map = list_map(((x.paper_id,x) for x in names))
    return [(x, ref_map.get(x.pk,[]), name_map.get(x.pk,[]))
        for x in paper_list]

class PageNavigator(object):
    def __init__(self, request, object_list, per_page=25, arg_name=None):
        self.request = request
        self.object_list = object_list
        self.arg_name = arg_name or 'page'
        self.paginator = paginator.Paginator(object_list, per_page)
        try:
            self.page = self.paginator.page(request.GET.get(self.arg_name, 1))
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
