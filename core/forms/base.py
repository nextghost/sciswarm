from django import forms
from django.utils.html import mark_safe
from django.utils.translation import ugettext as _
from .widgets import SubmitButton
from ..utils.utils import logger
from ..utils.transaction import lock_record

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
