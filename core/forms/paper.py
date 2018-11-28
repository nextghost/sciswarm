from django.core.exceptions import ImproperlyConfigured
from django.forms import fields, modelformset_factory, widgets, ValidationError
from django.utils.translation import ugettext_lazy as _
from .base import ModelForm, BaseAliasForm
from ..models import const
from ..utils.transaction import lock_record
from ..utils.validators import validate_paper_alias
from .. import models
import re

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
