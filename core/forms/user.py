from django.core.exceptions import ImproperlyConfigured
from django.forms import modelformset_factory, ValidationError
from django.utils.translation import ugettext_lazy as _
from .base import ModelForm, BaseAliasForm
from ..models import const
from ..utils.transaction import lock_record
from ..utils.validators import validate_person_alias
from .. import models

class UserAliasForm(BaseAliasForm):
    class Meta:
        model = models.UserAlias
        fields = ('scheme', 'identifier')

    def validate_alias(self, scheme, identifier):
        return validate_person_alias(scheme, identifier)

UserAliasFormset = modelformset_factory(models.UserAlias, form=UserAliasForm)

# This form must be processed and saved under transaction
class PaperAuthorForm(UserAliasForm):
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
            aliastab = models.UserAlias.query_model
            reftab = models.PaperAuthorReference.query_model
            refobjs = models.PaperAuthorReference.objects

            query = ((aliastab.scheme == scheme) &
                (aliastab.identifier == identifier))
            alias = models.UserAlias.objects.filter(query).first()

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
        query = (models.UserAlias.query_model.pk == ret.pk)
        if not self.parent.authors.filter(query).exists():
            models.PaperAuthorReference.objects.create(paper=self.parent,
                author_alias=ret, confirmed=None)
        return ret

    save.alters_data = True
