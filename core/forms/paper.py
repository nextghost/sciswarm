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
from django.forms import fields, modelformset_factory, widgets, ValidationError
from django.urls import reverse
from django.utils.html import mark_safe
from django.utils.translation import ugettext_lazy as _
from .base import Form, ModelForm, BaseAliasForm
from .widgets import SubmitButton
from ..models import const
from ..utils import pgsql, sql
from ..utils.transaction import lock_record
from ..utils.utils import fold_and, fold_or
from ..utils.validators import validate_paper_alias, validate_person_alias
from .. import models
import re

class PaperSearchForm(Form):
    title = forms.CharField(label=_('Title'), required=False)
    year_published = forms.IntegerField(label=_('Year published'),
        required=False)
    author = forms.CharField(label=_('Author'), required=False,
        help_text=_('Author name or identifier.'))
    identifier = forms.CharField(label=_('Identifier'), required=False)
    keywords = forms.CharField(label=_('Keywords'), required=False,
        help_text=_('Comma-separated list of keywords.'))

    def __init__(self, *args, **kwargs):
        queryset = kwargs.pop('queryset', None)
        if queryset is None:
            msg = '"queryset" keyword argument is required'
            raise ImproperlyConfigured(msg)
        super(PaperSearchForm, self).__init__(*args, **kwargs)
        self.queryset = queryset
        self.fields['year_published'].widget.attrs['size'] = 6

    def clean(self):
        papertab = sql.Table(models.Paper)
        join = papertab
        cond_list = []

        # Paper title
        title = self.cleaned_data.get('title')
        if title:
            cond_list.append(papertab.name.icontains(title))

        # Year published
        year_published = self.cleaned_data.get('year_published')
        if year_published is not None:
            cond_list.append(papertab.year_published == year_published)

        # Author name/identifier
        author = self.cleaned_data.get('author')
        if author:
            reftab = sql.Table(models.PaperAuthorReference)
            # aliastab: author identifier referenced by the paper
            # (may be unlinked)
            aliastab = sql.Table(models.PersonAlias)
            # extaliastab: all identifiers of the linked author whether or not
            # they're referenced by the paper itself
            extaliastab = sql.Table(models.PersonAlias)
            cond = (reftab.author_alias_id == aliastab.pk)
            subjoin = reftab.inner_join(aliastab, cond)
            cond = (aliastab.target_id == extaliastab.target_id)
            subjoin = subjoin.left_join(extaliastab, cond)

            if ':' in author:
                # Scheme prefix in input, search only identifiers
                try:
                    scheme, identifier = validate_person_alias('', author)
                    cond = ((papertab.pk == reftab.paper_id) &
                        (((aliastab.scheme == scheme) &
                        (aliastab.identifier == identifier)) |
                        ((extaliastab.scheme == scheme) &
                        (extaliastab.identifier == identifier))))
                    join = join.inner_join(subjoin, cond)
                except ValidationError as err:
                    self.add_error('author', err)
            else:
                persontab = sql.Table(models.Person)
                nametab = sql.Table(models.PaperAuthorName)
                cond = (aliastab.target_id == persontab.pk)
                subjoin = subjoin.left_join(persontab, cond)

                # Search author aliases and linked users
                tokens = author.split()
                tmplist = [(persontab.first_name.icontains(x) |
                    persontab.last_name.icontains(x)) for x in tokens]
                tmplist.append(aliastab.identifier == author)
                tmplist.append(extaliastab.identifier == author)
                cond = (papertab.pk == reftab.paper_id)
                join = join.left_join(subjoin, cond & fold_or(tmplist))

                # Search plain author names
                tmplist = [nametab.author_name.icontains(x) for x in tokens]
                tmplist.append(papertab.pk == nametab.paper_id)
                join = join.left_join(nametab, fold_and(tmplist))
                cond_list.append(aliastab.pk.notnull() | nametab.pk.notnull())

        # Paper identifier
        identifier = self.cleaned_data.get('identifier')
        if identifier:
            aliastab = sql.Table(models.PaperAlias)
            cond = (papertab.pk == aliastab.target_id)
            if ':' in identifier:
                try:
                    scheme, identifier = validate_paper_alias('', identifier)
                    cond &= (aliastab.scheme == scheme)
                except ValidationError as err:
                    self.add_error('identifier', err)
            if not self.has_error('identifier'):
                cond &= (aliastab.identifier == identifier)
                join = join.inner_join(aliastab, cond)

        # Paper keywords (multiple)
        keywords = self.cleaned_data.get('keywords')
        if keywords:
            kw_list = [x.strip() for x in keywords.split(',')]
            for kw in kw_list:
                if not kw:
                    continue
                kwtab = sql.Table(models.PaperKeyword)
                cond = ((papertab.pk == kwtab.paper_id) &
                    (sql.upper(kwtab.keyword) == kw.upper()))
                join = join.inner_join(kwtab, cond)

        # Filter queryset
        sub = join.select(papertab.pk, where=fold_and(cond_list))
        query = models.Paper.query_model.pk.belongs(sub)
        self.queryset = self.queryset.filter(query)

class PaperForm(ModelForm):
    class Meta:
        model = models.Paper
        fields = ('name', 'abstract', 'contents_theory', 'contents_survey',
            'contents_observation', 'contents_experiment',
            'contents_metaanalysis', 'year_published', 'cite_as',
            'incomplete_metadata', 'keywords')
    keywords = fields.CharField(label=_('Keywords'), required=False,
        help_text=_('List of keywords separated by commas or newlines.'),
        widget=widgets.Textarea)

    def __init__(self, *args, **kwargs):
        super(PaperForm, self).__init__(*args, **kwargs)
        if self.instance.pk is None:
            self.fields['own_paper'] = fields.BooleanField(initial=True,
                label=_('I am an author'), required=False)
        else:
            qs = self.instance.paperkeyword_set.all()
            keyword_list = [x.keyword for x in qs]
            self.initial['keywords'] = ', '.join(keyword_list)
        self.keyword_set = set()

    def clean_keywords(self):
        text = self.cleaned_data.get('keywords', '')
        kwlist = re.split('[,\n]+', text, flags=re.MULTILINE)
        ret = set((x for x in map(lambda y: y.strip(), kwlist) if x))
        mfield = models.PaperKeyword._meta.get_field('keyword')
        if max((len(x) for x in ret)) > mfield.max_length:
            msg=_('Some keywords are longer than %(limit_value)s characters.')
            params = dict(limit_value=mfield.max_length)
            raise ValidationError(msg, 'max_value', params=params)
        return ret

    def clean(self):
        if self.instance.pk is not None:
            tmp = lock_record(self.instance)
            if tmp is None:
                msg = _('Database error, please try again later.')
                raise ValidationError(msg, 'lock')
            self.instance = tmp
            qs = self.instance.paperkeyword_set.all()
            self.keyword_set = set((x.keyword for x in qs))

    def save(self):
        # Find poster's main alias if needed
        author = None
        new_paper = self.instance.pk is None
        if new_paper and self.cleaned_data.get('own_paper'):
            alias_tab = models.PersonAlias.query_model
            alias_objs = models.PersonAlias.objects
            query = (alias_tab.target == self.instance.posted_by)
            query2 = (alias_tab.scheme == const.person_alias_schemes.SCISWARM)
            author = alias_objs.filter(query & query2).order_by('pk').first()
            if author is None:
                author = alias_objs.filter(query).order_by('pk').first()
        ret = super(PaperForm, self).save()

        # Update keywords
        new_keywords = self.cleaned_data.get('keywords', set())
        if new_keywords != self.keyword_set:
            del_keywords = list(self.keyword_set - new_keywords)
            add_keywords = [models.PaperKeyword(paper=ret, keyword=x)
                for x in (new_keywords - self.keyword_set)]
            if del_keywords:
                kwtab = models.PaperKeyword.query_model
                query = kwtab.keyword.belongs(del_keywords)
                ret.paperkeyword_set.filter(query).delete()
            if add_keywords:
                models.PaperKeyword.objects.bulk_create(add_keywords)

        # Create permanent identifier and add poster as author if appropriate
        if new_paper:
            scheme = const.paper_alias_schemes.SCISWARM
            models.PaperAlias.objects.link_alias(scheme, 'p/'+str(ret.pk), ret)
            models.FeedEvent.objects.create(person=ret.posted_by, paper=ret,
                event_type=const.user_feed_events.PAPER_POSTED)
        if author is not None:
            models.PaperAuthorReference.objects.create(paper=ret,
                author_alias=author, confirmed=True)
        return ret

    save.alters_data = True

class PaperAliasForm(BaseAliasForm):
    class Meta:
        model = models.PaperAlias
        fields = ('scheme', 'identifier')

    def validate_alias(self, scheme, identifier):
        return validate_paper_alias(scheme, identifier)

PaperAliasFormset = modelformset_factory(models.PaperAlias,
    form=PaperAliasForm)

class PaperAuthorNameForm(ModelForm):
    class Meta:
        model = models.PaperAuthorName
        fields = ('author_name',)
    # Set instance.paper in view.form_valid(), not in form.save()

PaperAuthorNameFormset = modelformset_factory(models.PaperAuthorName,
    form=PaperAuthorNameForm)

class PaperSupplementalLinkForm(ModelForm):
    class Meta:
        model = models.PaperSupplementalLink
        fields = ('name', 'url')

    def __init__(self, *args, **kwargs):
        super(PaperSupplementalLinkForm, self).__init__(*args, **kwargs)
        if self.instance.pk is None:
            if not self.initial.get('paper'):
                raise ImproperlyConfigured('"paper" initial value is required')
            self.instance.paper = self.initial['paper']

    def clean(self):
        if self.instance.pk is None:
            paper = self.initial['paper']
        else:
            paper = self.instance.paper
        lock_record(paper)

        table = models.PaperSupplementalLink.query_model
        name = self.cleaned_data.get('name')
        url = self.cleaned_data.get('url')
        query1 = (table.name == name)
        query2 = (table.url == url)
        if self.instance.pk is not None:
            query1 &= (table.pk != self.instance.pk)
            query2 &= (table.pk != self.instance.pk)
        if paper.papersupplementallink_set.filter(query1).exists():
            msg = _('This paper already has a link with this name.')
            self.add_error('name', ValidationError(msg, 'unique'))
        if paper.papersupplementallink_set.filter(query2).exists():
            msg = _('This paper already has this link.')
            self.add_error('url', ValidationError(msg, 'unique'))

# This form must be processed and saved under transaction
class PaperRecommendationForm(Form):
    def __init__(self, *args, **kwargs):
        person = kwargs.pop('person')
        paper = kwargs.pop('paper')
        if person is None:
            raise ImproperlyConfigured('"person" keyword argument is required')
        if paper is None:
            raise ImproperlyConfigured('"paper" keyword argument is required')
        super(PaperRecommendationForm, self).__init__(*args, **kwargs)
        self.person = person
        self.paper = paper
        self.recommended = self._recommendation_queryset().exists()

    def _recommendation_queryset(self):
        evtab = models.FeedEvent.query_model
        query = ((evtab.person == self.person) & (evtab.paper == self.paper) &
            (evtab.event_type == const.user_feed_events.PAPER_RECOMMENDATION))
        return models.FeedEvent.objects.filter(query)

    def get_buttons(self):
        if self.recommended:
            return (('_unrecommend', _('Cancel recommendation')),)
        else:
            return (('_recommend', _('Recommend')),)

    def submit_buttons(self):
        button = SubmitButton()
        ret = [button.render(name, title) for name,title in self.get_buttons()]
        return mark_safe(' '.join(ret))

    def clean(self):
        lock_record(self.person)
        self.recommended = self._recommendation_queryset().exists()

    def save(self):
        event_type = const.user_feed_events.PAPER_RECOMMENDATION
        if '_recommend' in self.data and not self.recommended:
            models.FeedEvent.objects.create(person=self.person,
                paper=self.paper, event_type=event_type)
        elif '_unrecommend' in self.data and self.recommended:
            self._recommendation_queryset().delete()

    save.alters_data = True

class ScienceSubfieldForm(ModelForm):
    class Meta:
        model = models.ScienceSubfield
        fields = ('field', 'subfield', 'name')
    subfield = forms.ModelChoiceField(label=_('Subfield'), required=False,
        queryset=models.ScienceSubfield.objects.none(),
        empty_label=_('Other:'))

    def __init__(self, *args, **kwargs):
        # Paper may be None.
        paper = kwargs.pop('paper', None)
        super(ScienceSubfieldForm, self).__init__(*args, **kwargs)
        self.paper = paper
        widget = self.fields['field'].widget
        widget.attrs['data-reload-select'] = self.add_prefix('subfield')
        widget.attrs['data-callback'] = reverse('core:ajax_science_subfields')
        self.fields['name'].required = False
        if self.data is not None:
            value = self.data.get(self.add_prefix('field'))
            if value is not None:
                sftab = models.ScienceSubfield.query_model
                sfobj = models.ScienceSubfield.objects
                query = (sftab.field == value)
                self.fields['subfield'].queryset = sfobj.filter(query)

    def clean(self):
        sftab = models.ScienceSubfield.query_model
        sfobj = models.ScienceSubfield.objects
        field = self.cleaned_data.get('field')
        subfield = self.cleaned_data.get('subfield')

        # Creating new subfield, validate name
        if subfield is None:
            name = self.cleaned_data.get('name')
            if name is not None:
                name = name.strip().title()
                self.cleaned_data['name'] = name
            if name:
                if field is not None:
                    pgsql.lock_table(models.ScienceSubfield,
                        pgsql.LOCK_SHARE_UPDATE_EXCLUSIVE)
                    query = (sftab.name == name)
                    tmp = sfobj.filter(query).first()
                    if tmp is not None:
                        if tmp.field == field:
                            self.cleaned_data['subfield'] = tmp
                        else:
                            msg = _('This subfield already exists under %s.')
                            msg = msg % const.science_fields[tmp.field]
                            err = ValidationError(msg, 'unique')
                            self.add_error('name', err)
            # if subfield is None and (not name) and...
            elif not (self.has_error('name') or self.has_error('subfield')):
                msg = _('Select a subfield from the list or enter new subfield name.')
                self.add_error('name', ValidationError(msg, 'required'))

    def save(self):
        if self.errors:
            msg = 'Form cannot be saved because input validation failed.'
            raise ValueError(msg)
        subfield = self.cleaned_data.get('subfield')
        if subfield is None:
            sfobj = models.ScienceSubfield.objects
            field = self.cleaned_data.get('field')
            name = self.cleaned_data.get('name')
            subfield = sfobj.create(field=field, name=name)
        if self.paper is not None:
            lock_record(self.paper)
            if not self.paper.fields.filter(pk=subfield.pk).exists():
                self.paper.fields.add(subfield)
                self.paper.save(update_fields=['last_changed', 'changed_by'])
        return subfield

    save.alters_data = True
