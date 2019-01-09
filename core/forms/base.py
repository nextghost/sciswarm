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

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError
from django.utils.html import conditional_escape, format_html, mark_safe
from django.utils.translation import ugettext as _
from .widgets import SubmitButton
from ..models import const
from ..utils.utils import logger
from ..utils.transaction import lock_record
from ..utils.validators import validate_alias

class HelpTextMixin(object):
    def __getitem__(self, name):
        ret = super(HelpTextMixin, self).__getitem__(name)
        if not ret.is_hidden:
            field = self.fields[name]
            if field.help_text and not field.widget.attrs.get('title'):
                field.widget.attrs['title'] = field.help_text
        return ret

    def as_table(self):
        "Returns this form rendered as HTML <tr>s -- excluding the <table></table>."
        return self._html_output(
            normal_row='<tr%(html_class_attr)s><th>%(label)s</th><td>%(errors)s%(field)s</td></tr>',
            error_row='<tr><td colspan="2">%s</td></tr>',
            row_ender='</td></tr>',
            help_text_html='%s',
            errors_on_separate_row=False)

    def as_ul(self):
        "Returns this form rendered as HTML <li>s -- excluding the <ul></ul>."
        return self._html_output(
            normal_row='<li%(html_class_attr)s>%(errors)s%(label)s %(field)s</li>',
            error_row='<li>%s</li>',
            row_ender='</li>',
            help_text_html='%s',
            errors_on_separate_row=False)

    def as_p(self):
        "Returns this form rendered as HTML <p>s."
        return self._html_output(
            normal_row='<p%(html_class_attr)s>%(label)s %(field)s</p>',
            error_row='%s',
            row_ender='</p>',
            help_text_html='%s',
            errors_on_separate_row=True)

class Form(HelpTextMixin, forms.Form):
    pass

class ModelForm(HelpTextMixin, forms.ModelForm):
    pass

class BaseUpdateForm(ModelForm):
    def __init__(self, *args, **kwargs):
        if kwargs.get('instance') is None:
            raise ImproperlyConfigured("'instance' argument required")
        super(BaseUpdateForm, self).__init__(*args, **kwargs)

class TransactionForm(ModelForm):
    def lock_field(self, fieldname):
        data = self.cleaned_data.get(fieldname)
        if data is not None:
            data = lock_record(data)
            if data is None:
                msg = _('Invalid value')
                err = forms.ValidationError(msg, 'invalid')
                self.add_error(fieldname, err)
        return data

class StateChangeForm(Form):
    """Base class for state change actions with no visible fields"""

    def __init__(self, *args, **kwargs):
        instance = kwargs.pop('instance', None)
        if instance is None:
            raise ImproperlyConfigured("'instance' argument required")
        super(StateChangeForm, self).__init__(*args, **kwargs)
        self.instance = instance
        self.update_fields = None

    def get_buttons(self):
        # return format: ((name1, title1), (name2, title2), ...)
        raise NotImplementedError('Override this method in subclass')

    def submit_buttons(self):
        button = SubmitButton()
        ret = [button.render(name, title) for name,title in self.get_buttons()]
        return mark_safe(' '.join(ret))

    def save(self, commit=True):
        for name, title in self.get_buttons():
            if name in self.data:
                getattr(self, name)()
                break
        else:
            msg = '%s.save() called but no valid action selected'
            logger.warning(msg, type(self).__name__)
            return self.instance
        if commit:
            self.instance.save(update_fields=self.update_fields)
        return self.instance

    save.alters_data = True

    def as_table(self):
        return ''

    def as_ul(self):
        return ''

    def as_p(self):
        return ''

class BaseAliasForm(ModelForm):
    def __init__(self, *args, **kwargs):
        allow_sciswarm = kwargs.pop('allow_sciswarm', False)
        require_unlinked = kwargs.pop('require_unlinked', False)
        label = kwargs.pop('label', _('Identifier:'))
        super(BaseAliasForm, self).__init__(*args, **kwargs)
        self.allow_sciswarm = allow_sciswarm
        self.require_unlinked = require_unlinked
        self.label = label
        if self.instance.pk is not None:
            msg = 'Editing existing aliases is not allowed.'
            raise ImproperlyConfigured(msg)
        if not self.allow_sciswarm:
            field = self.fields['scheme']
            blocked = const.person_alias_schemes.SCISWARM
            field.choices = [(k,v) for (k,v) in field.choices if k != blocked]

    def _html_output(self, template):
        scheme = self['scheme']
        ident = self['identifier']
        err_list = [y for x in self.errors.values() for y in x]
        errors = self.error_class([conditional_escape(e) for e in err_list])
        return format_html(template, label=self.label, errors=errors,
            scheme=scheme, identifier=ident)

    def as_table(self):
        tpl = '<tr><th>{label}</th><td>{errors}{scheme}{identifier}</tr>'
        return self._html_output(tpl)

    def as_ul(self):
        tpl = '<li>{errors}{label} {scheme}{identifier}</li>'
        return self._html_output(tpl)

    def as_p(self):
        tpl = '{errors}\n<p>{label} {scheme}{identifier}</p>'
        return self._html_output(tpl)

    def validate_alias(self, scheme, identifier):
        return validate_alias(scheme, identifier)

    def clean(self):
        scheme = self.cleaned_data.get('scheme')
        identifier = self.cleaned_data.get('identifier')
        target = self.instance.target or self.initial.get('target')

        if identifier:
            try:
                (scheme, identifier) = self.validate_alias(scheme, identifier)
                self.cleaned_data['scheme'] = scheme
                self.cleaned_data['identifier'] = identifier
            except forms.ValidationError as err:
                self.add_error('identifier', err)
                scheme = None
                identifier = None
        if scheme:
            maxlen = self._meta.model._meta.get_field('scheme').max_length
            if len(scheme) > maxlen:
                msg = _('Scheme prefix is too long.')
                err = forms.ValidationError(msg, 'max_length')
                self.add_error('identifier', err)
        if not self.allow_sciswarm:
            if scheme == const.person_alias_schemes.SCISWARM:
                msg = _('This scheme prefix is not allowed.')
                err = forms.ValidationError(msg, 'invalid')
                self.add_error('identifier', err)
        if ((self.require_unlinked or target is not None) and
            not (self.has_error('identifier') or self.has_error('scheme'))):
            objs = self._meta.model.objects
            if not objs.check_alias_available(scheme, identifier, target):
                msg = _('This identifier is already in use.')
                err = forms.ValidationError(msg, 'unique')
                self.add_error('identifier', err)

    def save(self, commit=True):
        target = self.instance.target or self.initial.get('target')
        objs = self._meta.model.objects
        tmp = super(BaseAliasForm, self).save(commit=False)

        if target is None:
            return objs.create_alias(tmp.scheme, tmp.identifier)

        try:
            return objs.link_alias(tmp.scheme, tmp.identifier, target)
        except IntegrityError:
            msg = _('This identifier is already in use.')
            err = forms.ValidationError(msg, 'unique')
            self.add_error('identifier', err)
            raise

    save.alters_data = True
