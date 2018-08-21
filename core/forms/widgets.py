from django.forms import widgets
from django.forms.utils import flatatt
from django.utils.html import format_html, mark_safe

class AutocompleteWidget(widgets.TextInput):
    def build_attrs(self, *args, **kwargs):
        ret = super(AutocompleteWidget, self).build_attrs(*args, **kwargs)
        cls = ret.get('class') or ''
        cls_items = cls.split()
        if 'autocomplete' not in cls_items:
            cls_items.append('autocomplete')
        ret['class'] = ' '.join(cls_items)
        ret['autocomplete'] = 'off'
        ret['data-callback'] = self.callback_url
        return ret

    def render(self, name, value, attrs=None):
        ret = super(AutocompleteWidget, self).render(name, value, attrs)
        box_attrs = {'class': 'suggest_box', 'id': name+'_suggest'}
        suggestion_box = format_html('<div{}></div>', flatatt(box_attrs))
        return mark_safe(ret + suggestion_box)

class SubmitButton(widgets.Input):
    input_type = 'submit'

    def build_attrs(self, *args, **kwargs):
        ret = super(SubmitButton, self).build_attrs(*args, **kwargs)
        if not ret.get('name'):
            ret.pop('name', None)
        return ret
