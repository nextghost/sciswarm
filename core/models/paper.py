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

from django.db import models, transaction, IntegrityError
from django.http import QueryDict
from django.urls import reverse
from django.utils.html import format_html, mark_safe
from django.utils.translation import ugettext_lazy as _
from ..utils import html
from . import auth, const

class AliasManager(models.Manager):
    def check_alias_available(self, scheme, identifier, target=None):
        table = self.model.query_model
        query = ((table.scheme == scheme) & (table.identifier == identifier) &
            table.target.notnull())
        if target is not None:
            query &= (table.target != target)
        return not self.filter(query).exists()

    def create_alias(self, scheme, identifier):
        table = self.model.query_model
        query = ((table.scheme == scheme) & (table.identifier == identifier))
        qs = self.filter(query)
        try:
            return qs.get()
        except self.model.DoesNotExist:
            pass

        try:
            # Savepoint to avoid crashing any parent transaction
            with transaction.atomic():
                return self.create(scheme=scheme, identifier=identifier)
        except IntegrityError:
            return qs.get()

    # This method must be called under a transaction
    def link_alias(self, scheme, identifier, target):
        if target is None:
            raise ValueError('Invalid target')
        table = self.model.query_model
        query = ((table.scheme == scheme) & (table.identifier == identifier))
        qs = self.select_for_update().filter(query)

        def link_existing():
            ret = qs.get()
            if ret.target_id is not None and ret.target_id != target.pk:
                raise IntegrityError('Alias already in use.')
            ret.target = target
            ret.save()
            return ret

        # SELECT FOR UPDATE doesn't prevent INSERT race condition on PGSQL
        try:
            return link_existing()
        except self.model.DoesNotExist:
            pass

        try:
            # Savepoint to avoid crashing the whole transaction
            with transaction.atomic():
                return self.create(scheme=scheme, identifier=identifier,
                    target=target)
        except IntegrityError:
            return link_existing()

class UserAlias(models.Model):
    class Meta:
        unique_together = (('scheme', 'identifier'),)
        ordering = ('scheme', 'identifier')
    objects = AliasManager()

    scheme = models.CharField(_('scheme'), max_length=16, blank=True,
        choices=const.person_alias_schemes.items())
    identifier = models.CharField(_('identifier'), max_length=150)
    target = models.ForeignKey(auth.User, verbose_name=_('user'), null=True,
        on_delete=models.SET_NULL)

    def __str__(self):
        if self.scheme == const.person_alias_schemes.URL:
            return self.identifier
        prefix = const.person_alias_schemes.get(self.scheme)
        if prefix is None:
            return ':'.join((self.scheme, self.identifier))
        return ': '.join((str(prefix), self.identifier))

    def __html__(self):
        link = html.alias_link(self.scheme, self.identifier)
        prefix = const.person_alias_schemes.get(self.scheme)
        if prefix is None:
            return link
        return format_html('{prefix}: {link}', prefix=prefix, link=link)

    # Render link to self.target when possible, otherwise self.__html__()
    def target_link(self):
        if self.target_id is not None:
            url = self.target.get_absolute_url()
            return html.render_link(url, str(self.target))
        return self.__html__()

    def is_deletable(self):
        if self.scheme == const.person_alias_schemes.SCISWARM:
            return False
        elif self.scheme == const.person_alias_schemes.EMAIL:
            return self.identifier != self.target.email
        return True

    def unlink(self):
        table = self.__class__.query_model
        query = ((table.pk == self.pk) & (table.target.pk == self.target_id))
        self.__class__.objects.filter(query).update(target=None)

class PaperManager(models.Manager):
    def filter_public(self, value=True):
        return self.filter(public=value)

    def filter_by_author(self, author, confirmed=None):
        reftab = self.model.query_model.paperauthorreference
        query = (reftab.author_alias.target == author)
        if confirmed:
            query &= (reftab.confirmed == True)
        elif confirmed is not None:
            query &= (reftab.confirmed == False)
        return self.filter(query).distinct()

class Paper(models.Model):
    class Meta:
        ordering = ('name',)
    objects = PaperManager()

    name = models.CharField(_('title'), max_length=512, db_index=True)
    abstract = models.TextField(_('abstract'), max_length=4000)
    contents_theory = models.BooleanField(_('theory development'),
        help_text=_('Check this box if the paper expands prior theory.'),
        db_index=True)
    contents_survey = models.BooleanField(_('survey data'),
        help_text=_('Check this box if the paper contains or analyzes survey data.'),
        db_index=True)
    contents_observation = models.BooleanField(_('observational data'),
        help_text=_('Check this box if the paper contains or analyzes data from observation of natural phenomena.'),
        db_index=True)
    contents_experiment = models.BooleanField(_('experimental data'),
        help_text=_('Check this box if the paper contains or analyzes data from controlled experiments.'),
        db_index=True)
    contents_metaanalysis = models.BooleanField(_('metaanalysis'),
        help_text=_('Check this box if the paper contains extensive metaanalysis or literature review (aside from the usual summary in introduction).'),
        db_index=True)
    year_published = models.IntegerField(_('year published'), null=True,
        blank=True, db_index=True,
        help_text=_('Year when this paper was officially published, e.g. in a journal. Leave blank if publication date is pending.'))
    cite_as = models.CharField(_('cite as'), blank=True, max_length=512,
        help_text=_('Preferred citation text.'))
    incomplete_metadata = models.BooleanField(_('incomplete metadata'),
        help_text=_('Check this box if some information about this paper is missing (e.g. omitted citations because the cited papers have no usable identifier).'),
        db_index=True, default=True)
    date_posted = models.DateTimeField(_('date posted'), auto_now_add=True,
        db_index=True, editable=False)
    posted_by = models.ForeignKey(auth.User, verbose_name=_('posted by'),
        null=True, on_delete=models.SET_NULL, editable=False,
        related_name='posted_paper_set')
    last_changed = models.DateTimeField(_('last changed'), auto_now=True,
        db_index=True, editable=False)
    changed_by = models.ForeignKey(auth.User, verbose_name=_('changed by'),
        null=True, on_delete=models.SET_NULL, editable=False, related_name='+')
    # Public flag marks that the paper was taken down due to copyright claim
    public = models.BooleanField(_('public'), default=True)
    authors = models.ManyToManyField(UserAlias, through='PaperAuthorReference')
    bibliography = models.ManyToManyField('PaperAlias')

    def __str__(self):
        return self.name

    def contents_info(self):
        field_list = ['contents_theory', 'contents_survey',
            'contents_observation', 'contents_experiment',
            'contents_metaanalysis']
        ret = []
        for fname in field_list:
            if getattr(self, fname):
                field = self.__class__._meta.get_field(fname)
                ret.append(str(field.verbose_name))
        return ', '.join(ret).capitalize()

    def get_absolute_url(self):
        return reverse('core:paper_detail', kwargs=dict(pk=self.pk))

    # A paper is owned by all authors who didn't reject authorship.
    # If there are no linked authors, the paper will be provisionally owned
    # by whoever posted it.
    def is_owned_by(self, user):
        if user.is_superuser:
            return True
        uatab = UserAlias.query_model
        artab = uatab.paperauthorreference
        query = ((uatab.target.notnull()) & (artab.paper == self) &
            ((artab.confirmed == True) | (artab.confirmed.isnull())))
        qs = UserAlias.objects.filter(query).select_related('target')
        author_list = [x.target for x in qs]
        if user in author_list:
            return True
        return (not author_list) and user == self.posted_by

class PaperAlias(models.Model):
    class Meta:
        unique_together = (('scheme', 'identifier'),)
        ordering = ('scheme', 'identifier')
    objects = AliasManager()

    scheme = models.CharField(_('scheme'), max_length=16, blank=True,
        choices=const.paper_alias_schemes.items())
    identifier = models.CharField(_('identifier'), max_length=256)
    target = models.ForeignKey(Paper, verbose_name=_('paper'), null=True,
        on_delete=models.SET_NULL)

    def __str__(self):
        if self.scheme == const.paper_alias_schemes.URL:
            return self.identifier
        prefix = const.paper_alias_schemes.get(self.scheme)
        if prefix is None:
            return ':'.join((self.scheme, self.identifier))
        return ': '.join((str(prefix), self.identifier))

    def __html__(self):
        link = html.alias_link(self.scheme, self.identifier)
        prefix = const.paper_alias_schemes.get(self.scheme)
        if prefix is None:
            return link
        return format_html('{prefix}: {link}', prefix=prefix, link=link)

    # Render link to self.target when possible, otherwise self.__html__()
    def target_link(self):
        if self.target_id is not None:
            url = self.target.get_absolute_url()
            return html.render_link(url, str(self.target))
        return self.__html__()

    def unlink(self):
        table = self.__class__.query_model
        query = ((table.pk == self.pk) & (table.target.pk == self.target_id))
        self.__class__.objects.filter(query).update(target=None)

    def is_deletable(self):
        return self.scheme != const.person_alias_schemes.SCISWARM

class PaperKeyword(models.Model):
    class Meta:
        ordering = ('keyword',)
    keyword = models.CharField(_('keyword'), max_length=32, db_index=True)
    paper = models.ForeignKey(Paper, verbose_name=_('paper'),
        on_delete=models.CASCADE, editable=False)

    def __str__(self):
        return self.keyword

    def __html__(self):
        args = QueryDict(mutable=True)
        args['keywords'] = self.keyword
        tpl = '<a href="{url}">{title}</a>'
        url = reverse('core:paper_list') + '?' + args.urlencode()
        return format_html(tpl, url=url, title=self.keyword)

class PaperAuthorReferenceManager(models.Manager):
    def filter_unrejected(self, paper=None):
        table = self.model.query_model
        query = ((table.confirmed == True) | (table.confirmed.isnull()))
        if isinstance(paper, (list, tuple, models.QuerySet)):
            query &= table.paper.belongs(paper)
        elif paper is not None:
            query &= (table.paper == paper)
        return self.filter(query)

class PaperAuthorReference(models.Model):
    class Meta:
        ordering = ('paper', 'author_alias')
    objects = PaperAuthorReferenceManager()

    paper = models.ForeignKey(Paper, verbose_name=_('paper'),
        on_delete=models.CASCADE)
    author_alias = models.ForeignKey(UserAlias, verbose_name=_('author'),
        on_delete=models.CASCADE)
    confirmed = models.NullBooleanField(_('confirmed'), db_index=True)

    def __str__(self):
        ret = str(self.author_alias)
        if self.confirmed is None:
            ret += ' (?)'
        elif not self.confirmed:
            ret += ' (rejected)'
        return ret

    def __html__(self):
        content = self.author_alias.__html__()
        if self.confirmed is None:
            cls = 'author unconfirmed'
        elif self.confirmed:
            cls = 'author confirmed'
        else:
            cls = 'author rejected'
        return format_html('<span class="{cls}">{content}</span>', cls=cls,
            content=content)

    def target_link(self):
        content = self.author_alias.target_link()
        if self.confirmed is None:
            cls = 'author unconfirmed'
        elif self.confirmed:
            cls = 'author confirmed'
        else:
            cls = 'author rejected'
        return format_html('<span class="{cls}">{content}</span>', cls=cls,
            content=content)

    def status(self):
        if self.confirmed:
            return _('Confirmed')
        elif self.confirmed is None:
            return _('Pending')
        return _('Rejected')

# Table for author names without any identifier usable for deferred linking
class PaperAuthorName(models.Model):
    class Meta:
        ordering = ('paper', 'author_name')
    paper = models.ForeignKey(Paper, verbose_name=_('paper'),
        on_delete=models.CASCADE, editable=False)
    author_name = models.CharField(_('author'), max_length=128, db_index=True,
        help_text=_('Additional authors with no unique identifier'))

    def __str__(self):
        return self.author_name

class PaperSupplementalLink(models.Model):
    class Meta:
        ordering = ('paper', 'name')
        unique_together = (('name', 'paper'), ('url', 'paper'))
    paper = models.ForeignKey(Paper, verbose_name=_('paper'),
        on_delete=models.CASCADE, editable=False)
    name = models.CharField(_('title'), max_length=128)
    url = models.URLField(_('URL'), max_length=512)

    def __str__(self):
        return self.name

    def __html__(self):
        from ..utils.html import render_link
        return render_link(self.url, self.name)
