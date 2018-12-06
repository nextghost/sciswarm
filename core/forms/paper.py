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
from django.forms import fields, modelformset_factory, widgets, ValidationError
from django.utils.translation import ugettext_lazy as _
from .base import Form, ModelForm, BaseAliasForm
from ..models import const
from ..utils import sql
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
            aliastab = sql.Table(models.UserAlias)
            # extaliastab: all identifiers of the linked author whether or not
            # they're referenced by the paper itself
            extaliastab = sql.Table(models.UserAlias)
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
                usertab = sql.Table(models.User)
                nametab = sql.Table(models.PaperAuthorName)
                cond = (aliastab.target_id == usertab.pk)
                subjoin = subjoin.left_join(usertab, cond)

                # Search author aliases and linked users
                tokens = author.split()
                tmplist = [(usertab.first_name.icontains(x) |
                    usertab.last_name.icontains(x)) for x in tokens]
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
            alias_tab = models.UserAlias.query_model
            alias_objs = models.UserAlias.objects
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
        if author is not None:
            models.PaperAuthorReference.objects.create(paper=ret,
                author_alias=author, confirmed=True)
        return ret

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
