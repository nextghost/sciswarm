from django.http import QueryDict
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.encoding import force_text

def full_reverse(request, viewname, *args, **kwargs):
    url = reverse(viewname, *args, **kwargs)
    return request.build_absolute_uri(url)

def query_string(**kwargs):
    ret = QueryDict(mutable=True)
    ret.update(kwargs)
    return ret.urlencode()

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
