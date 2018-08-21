# -*- coding: utf-8 -*-
from django import template
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.forms.utils import flatatt
from django.http import QueryDict
from django.template.defaultfilters import stringfilter
from django.template import defaulttags
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import ugettext as _
from .. import models

register = template.Library()

@register.filter(name='getattr')
def filter_getattr(obj, name):
    if isinstance(name, six.text_type) and name.startswith('_'):
        msg = 'Variables and attributes may not begin with underscores: %s'
        raise template.TemplateSyntaxError(msg % name)
    if isinstance(name, six.text_type) and hasattr(obj, name):
        ret = getattr(obj, name)
    else:
        try:
            ret = obj[name]
        except (KeyError, IndexError):
            return ''
    if callable(ret):
        if getattr(ret, 'do_not_call_in_templates', False):
            pass
        elif getattr(ret, 'alters_data', False):
            msg = 'Method "%s" alters data, use in templates not allowed'
            raise template.TemplateSyntaxError(msg % name)
        else:
            return ret()
    return ret

@register.filter(name='enumerate')
def filter_enumerate(data, start=0):
    return enumerate(data, start)

@register.filter(name='abs')
def filter_abs(value):
    return abs(value)

@register.filter
def rmod(left, right):
    return right % left

@register.filter
def object_link(obj):
    if (not hasattr(obj, 'name')) or not hasattr(obj, 'get_absolute_url'):
        raise template.TemplateSyntaxError('Cannot build link for this object')
    kwargs = dict(name=obj.name, url=obj.get_absolute_url())
    return format_html('<a href="{url}">{name}</a>', **kwargs)

@register.filter
@stringfilter
def email(value):
    box, tmp, domain = value.partition('@')
    display = value.replace('@', _('(at)'), 1)
    args = {'class': 'maillink', 'data-box': box, 'data-domain': domain}
    template = '<span{attr}>{content}</span><script type="text/javascript">sciswarm_unmask();</script>'
    return format_html(template, attr=flatatt(args), content=display)

def parse_var_block(parser, token, endblock):
    try:
        tag_name, objvar = token.split_contents()
    except ValueError:
        msg = "%r tag requires exactly one argument"
        raise template.TemplateSyntaxError(msg % token.contents.split()[0])
    block = parser.parse(endblock)
    ntoken = parser.next_token()
    return (objvar, block, ntoken)

@register.tag
def ifown(parser, token):
    elblock = None
    objvar, block, ntoken = parse_var_block(parser, token, ('endifown','else'))
    if ntoken.contents == 'else':
        elblock = parser.parse(('endifown',))
        parser.delete_first_token()
    return IfOwnNode(objvar, block, elblock)

@register.tag
def ifeditable(parser, token):
    objvar, block, ntoken = parse_var_block(parser, token, ('endifeditable',))
    return IfEditableNode(objvar, block)

@register.tag
def full_url(parser, token):
    return FullURLNode(defaulttags.url(parser, token))

@register.tag
def login_url(parser, token):
    line = token.split_contents()
    as_var = None
    if len(line) == 3 and line[1] == 'as':
        as_var = line[2]
    elif len(line) != 1:
        msg = "Invalid arguments for tag %r"
        raise template.TemplateSyntaxError(msg % line[0])
    return LoginURLNode(as_var)

@register.simple_tag(takes_context=True)
def current_url(context):
    return context['request'].get_full_path()

class IfOwnNode(template.Node):
    def __init__(self, objvar, block, elblock=None):
        self.objvar = template.Variable(objvar)
        self.block = block
        self.elblock = elblock

    def render(self, context):
        try:
            obj = self.objvar.resolve(context)
            if obj.is_own(context['request']):
                return self.block.render(context)
            elif self.elblock is not None:
                return self.elblock.render(context)
            return ''
        except (KeyError, template.VariableDoesNotExist):
            return ''

class IfEditableNode(template.Node):
    def __init__(self, objvar, block):
        self.objvar = template.Variable(objvar)
        self.block = block

    def render(self, context):
        try:
            obj = self.objvar.resolve(context)
            if not obj.is_own(context['request']):
                return ''
            if hasattr(obj, 'editable') and not obj.editable:
                return ''
            return self.block.render(context)
        except (KeyError, template.VariableDoesNotExist):
            return ''

class FullURLNode(template.Node):
    def __init__(self, subnode):
        self.subnode = subnode

    def render(self, context):
        url = self.subnode.render(context)
        if not self.subnode.asvar:
            return context['request'].build_absolute_uri(url)
        var = self.subnode.asvar
        context[var] = context['request'].build_absolute_uri(context[var])
        return ''

class LoginURLNode(template.Node):
    def __init__(self, as_var=None):
        self.as_var = as_var

    def render(self, context):
        request = context['request']
        url = reverse('login')
        path = request.get_full_path()
        args = QueryDict(mutable=True)
        args[REDIRECT_FIELD_NAME] = path
        ret = ''.join([url, '?', args.urlencode(safe='/')])
        if self.as_var:
            context[self.as_var] = ret
            return ''
        return ret

class OwnCompanyURLNode(template.Node):
    def render(self, context):
        request = context['request']
        company = models.Company.objects.get_own(request)
        return company.get_absolute_url()
