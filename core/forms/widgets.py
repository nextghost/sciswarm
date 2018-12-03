# This file is part of Sciswarm, a scientific social network
# Copyright (C) 2018 Martin Doucha
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
