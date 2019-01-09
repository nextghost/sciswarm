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

from django.forms.utils import flatatt
from django.http import QueryDict
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.encoding import force_text
from django.utils.translation import ugettext as _
from ..models import const

def full_reverse(request, viewname, *args, **kwargs):
    url = reverse(viewname, *args, **kwargs)
    return request.build_absolute_uri(url)

def query_string(**kwargs):
    ret = QueryDict(mutable=True)
    ret.update(kwargs)
    return ret.urlencode()

def render_link(url, title, attrs={}):
    tpl = '<a href="{url}"{attr}>{title}</a>'
    return format_html(tpl, url=url, attr=flatatt(attrs), title=title)

def raw_scheme_link(scheme, identifier):
    return render_link(':'.join((scheme, identifier)), identifier)

def email_link(scheme, identifier):
    box, tmp, domain = identifier.partition('@')
    display = identifier.replace('@', _('(at)'), 1)
    args = {'class': 'maillink', 'data-box': box, 'data-domain': domain}
    template = '<span{attr}>{content}</span><script type="text/javascript">sciswarm_unmask();</script>'
    return format_html(template, attr=flatatt(args), content=display)

def web_link(scheme, identifier):
    return render_link(identifier, identifier)

def orcid_link(scheme, identifier):
    return render_link('https://orcid.org/' + identifier, identifier)

def twitter_link(scheme, identifier):
    return render_link('https://twitter.com/' + identifier[1:], identifier)

def sciswarm_link(scheme, identifier):
    if identifier.startswith('u/'):
        kwargs = dict(username=identifier[2:])
        url = reverse('core:person_detail', kwargs=kwargs)
    elif identifier.startswith('p/'):
        url = reverse('core:paper_detail', kwargs=dict(pk=identifier[2:]))
    else:
        logger.info('Invalid sciswarm identifier: ' + identifier)
        return identifier
    return render_link(url, identifier)

def doi_link(scheme, identifier):
    return render_link('https://doi.org/' + identifier, identifier)

def arxiv_link(scheme, identifier):
    return render_link('https://arxiv.org/abs/' + identifier[6:], identifier)

_alias_linkgen_map = {
    const.person_alias_schemes.EMAIL: email_link,
    const.person_alias_schemes.ORCID: orcid_link,
    const.person_alias_schemes.XMPP: raw_scheme_link,
    const.person_alias_schemes.TWITTER: twitter_link,
    const.person_alias_schemes.SCISWARM: sciswarm_link,
    const.person_alias_schemes.URL: web_link,
    const.paper_alias_schemes.DOI: doi_link,
    const.paper_alias_schemes.ARXIV: arxiv_link,
}

def alias_link(scheme, identifier):
    linkgen = _alias_linkgen_map.get(scheme)
    if linkgen is not None:
        return linkgen(scheme, identifier)
    return identifier

class NavigationBar(object):
    def __init__(self, request, links, exclude_kwargs=[]):
        resolver = request.resolver_match
        exclude_set = set(exclude_kwargs)
        kwargs = dict(((k, v) for k, v in resolver.kwargs.items()
            if v is not None and k not in exclude_set))
        self.location = (resolver.view_name, tuple(resolver.args), kwargs)
        self.request = request
        self.links = links

    def __str__(self):
        links = []
        for title, urlname, args, kwargs in self.links:
            args = tuple((force_text(x) for x in args))
            kwargs = dict(((k, force_text(v)) for k, v in kwargs.items()))
            if (urlname, args, kwargs) == self.location:
                continue
            url = reverse(urlname, args=args, kwargs=kwargs)
            links.append((url, title))
        link_tpl = '<a href="{}">{}</a>'
        content = format_html_join(' | ', link_tpl, links)
        return format_html('<div class="navbar">{}</div>', content)
