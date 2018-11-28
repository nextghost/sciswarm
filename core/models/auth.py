from django.contrib.auth import models as auth_models
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
import datetime

class UserManager(auth_models.UserManager):
    def filter_active(self):
        table = self.model.query_model
        query = ((table.is_active == True) & table.verification_key.isnull())
        return self.filter(query)

class User(auth_models.AbstractUser):
    class Meta:
        ordering = ('last_name', 'first_name')
    objects = UserManager()

    title_before = models.CharField(_('titles before name'), max_length=64,
        blank=True)
    title_after = models.CharField(_('titles after name'), max_length=64,
        blank=True)
    language = models.CharField(_('system language'), max_length=8)
    bio = models.TextField(_('about you'), max_length=1024, blank=True)
    verification_key = models.CharField(_('e-mail verification key'),
        max_length=256, null=True, editable=False)
    delete_deadline = models.DateTimeField(_('account deletion date'),
        null=True, db_index=True, editable=False)

    def __str__(self):
        # This applies only to bots
        if (not self.first_name) or not self.last_name:
            return self.first_name or self.last_name
        args = dict(first_name=self.first_name, last_name=self.last_name)
        return _('{last_name}, {first_name}').format(**args)

    @property
    def name(self):
        return str(self)

    @property
    def full_name(self):
        args = dict(first_name=self.first_name, last_name=self.last_name,
            title_before=self.title_before, title_after=self.title_after)
        tokens = []
        if self.title_before:
            tokens.append('{title_before}')
        if self.first_name:
            tokens.append('{first_name}')
        if self.last_name:
            tokens.append('{last_name}')
        if self.title_after:
            tokens[-1] += ','
            tokens.append('{title_after}')
        tpl = ' '.join(tokens)
        return tpl.format(**args)

    def get_absolute_url(self):
        return reverse('core:user_detail', kwargs=dict(username=self.username))

    # Force logout when the user deletes their account
    def get_session_auth_hash(self):
        if self.delete_deadline is not None:
            return ''
        return super(User, self).get_session_auth_hash()

class BruteBlockManager(models.Manager):
    def purge_stale(self):
        start = timezone.now() - datetime.timedelta(hours=1)
        query = (BruteBlock.query_model.log_date < start)
        self.filter(query).delete()

class BruteBlock(models.Model):
    objects = BruteBlockManager()
    log_date = models.DateTimeField(auto_now_add=True, db_index=True)
    username = models.CharField(max_length=150, db_index=True)
    ip_address = models.GenericIPAddressField(db_index=True)

    @staticmethod
    def username_blocked(username):
        username = username[:BruteBlock._meta.get_field('username').max_length]
        table = BruteBlock.query_model
        query = (table.username == username)
        return BruteBlock.objects.filter(query).count() >= 20

    @staticmethod
    def client_blocked(request):
        table = BruteBlock.query_model
        query = (table.ip_address == request.META['REMOTE_ADDR'])
        return BruteBlock.objects.filter(query).count() >= 10

    @staticmethod
    def login_failure(request, username):
        username = username[:BruteBlock._meta.get_field('username').max_length]
        ip_address = request.META['REMOTE_ADDR']
        BruteBlock.objects.create(username=username, ip_address=ip_address)
        if BruteBlock.username_blocked(username):
            BruteLog.objects.create(username=username, ip_address=ip_address)
        elif BruteBlock.client_blocked(request):
            BruteLog.objects.create(ip_address=ip_address)

class BruteLog(models.Model):
    log_date = models.DateTimeField(auto_now_add=True, db_index=True)
    username = models.CharField(max_length=150, null=True)
    ip_address = models.GenericIPAddressField()
