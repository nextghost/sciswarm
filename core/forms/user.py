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

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.forms import modelformset_factory, ValidationError
from django.utils.html import mark_safe
from django.utils.translation import ugettext_lazy as _
from .base import Form, ModelForm, BaseAliasForm
from .widgets import SubmitButton
from ..models import const
from ..utils.transaction import lock_record
from ..utils.validators import validate_person_alias
from .. import models

class PersonAliasForm(BaseAliasForm):
    class Meta:
        model = models.PersonAlias
        fields = ('scheme', 'identifier')

    def validate_alias(self, scheme, identifier):
        return validate_person_alias(scheme, identifier)

PersonAliasFormset = modelformset_factory(models.PersonAlias,
    form=PersonAliasForm)

# This form must be processed and saved under transaction
class PaperAuthorForm(PersonAliasForm):
    def __init__(self, *args, **kwargs):
        paper = kwargs.pop('paper', None)
        if paper is None:
            raise ImproperlyConfigured('"paper" keyword argument is required')
        kwargs.setdefault('allow_sciswarm', True)
        super(PaperAuthorForm, self).__init__(*args, **kwargs)
        self.parent = paper

    def clean(self):
        lock_record(self.parent)
        super(PaperAuthorForm, self).clean()

        if not (self.has_error('scheme') or self.has_error('identifier')):
            scheme = self.cleaned_data.get('scheme')
            identifier = self.cleaned_data.get('identifier')
            aliastab = models.PersonAlias.query_model
            reftab = models.PaperAuthorReference.query_model
            refobjs = models.PaperAuthorReference.objects

            query = ((aliastab.scheme == scheme) &
                (aliastab.identifier == identifier))
            alias = models.PersonAlias.objects.filter(query).first()

            if alias is not None and alias.target_id is not None:
                # Check for previous authorship rejection
                query = ((reftab.paper == self.parent) &
                    (reftab.author_alias.target.pk == alias.target_id) &
                    (reftab.confirmed == False))
                if refobjs.filter(query).exists():
                    msg = _('This user has rejected authorship.')
                    err = ValidationError(msg, 'rejected')
                    self.add_error('identifier', err)

    def save(self):
        ret = super(PaperAuthorForm, self).save()
        query = (models.PersonAlias.query_model.pk == ret.pk)
        if not self.parent.authors.filter(query).exists():
            models.PaperAuthorReference.objects.create(paper=self.parent,
                author_alias=ret, confirmed=None)
        return ret

    save.alters_data = True

# This form must be processed and saved under transaction
class BaseAuthorshipConfirmationForm(Form):
    def __init__(self, *args, **kwargs):
        person = kwargs.pop('person', None)
        if person is None:
            raise ImproperlyConfigured('"person" keyword argument is required')
        super(BaseAuthorshipConfirmationForm, self).__init__(*args, **kwargs)
        self.person = person
        self.selected_papers = []

    def get_buttons(self):
        return (('_confirm_authorship', _('Confirm')),
            ('_reject_authorship', _('Reject')))

    def submit_buttons(self):
        button = SubmitButton()
        ret = [button.render(name, title) for name,title in self.get_buttons()]
        return mark_safe(' '.join(ret))

    def clean(self):
        action_count = len([x for x,y in self.get_buttons() if x in self.data])
        if action_count != 1:
            msg = _('Please choose whether to accept or reject authorship.')
            raise ValidationError(msg, 'no_action')
        # Lock papers where authorship is about to be confirmed/rejected
        pk_list = [x.pk for x in self.paper_list]
        query = models.Paper.query_model.pk.belongs(pk_list)
        models.Paper.objects.filter(query).select_for_update().first()

    def save(self):
        if not self.selected_papers:
            return
        table = models.PaperAuthorReference.query_model
        query = (table.paper.belongs(self.selected_papers) &
            (table.author_alias.target == self.person))
        qs = models.PaperAuthorReference.objects.filter(query)
        if '_confirm_authorship' in self.data:
            qs.update(confirmed=True)
        elif '_reject_authorship' in self.data:
            qs.update(confirmed=False)

    save.alters_data = True

class MassAuthorshipConfirmationForm(BaseAuthorshipConfirmationForm):
    def __init__(self, *args, **kwargs):
        paper_list = kwargs.pop('paper_list', None)
        if paper_list is None:
            msg = '"paper_list" keyword argument is required'
            raise ImproperlyConfigured(msg)
        super(MassAuthorshipConfirmationForm, self).__init__(*args, **kwargs)
        self.paper_list = list(paper_list)
        fname_tpl = 'select_%d'
        self.paper_fields = []
        for item in paper_list:
            fname = fname_tpl % item.pk
            self.fields[fname] = forms.BooleanField(required=False)
            self.paper_fields.append((item, fname))

    def clean(self):
        super(MassAuthorshipConfirmationForm, self).clean()
        fname_tpl = 'select_%d'
        self.selected_papers = [x for x in self.paper_list
            if self.cleaned_data.get(fname_tpl % x.pk, False)]

class AuthorshipConfirmationForm(BaseAuthorshipConfirmationForm):
    def __init__(self, *args, **kwargs):
        paper = kwargs.pop('instance', None)
        if paper is None:
            msg = '"instance" keyword argument is required'
            raise ImproperlyConfigured(msg)
        super(AuthorshipConfirmationForm, self).__init__(*args, **kwargs)
        self.paper_list = [paper]
        self.selected_papers = [paper]

    def clean(self):
        super(AuthorshipConfirmationForm, self).clean()
        paper = self.paper_list[0]
        revtab = models.PaperReview.query_model
        query = ((revtab.deleted == False) & (revtab.posted_by == self.person))
        qs = paper.paperreview_set.filter(query)
        if '_confirm_authorship' in self.data and qs.exists():
            msg = _('You cannot accept authorship of a paper which you have reviewed. You must delete the review first.')
            raise ValidationError(msg, 'selfpromo')

    def save(self):
        super(AuthorshipConfirmationForm, self).save()
        return self.paper_list[0]

    save.alters_data = True
