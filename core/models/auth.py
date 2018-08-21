from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
import datetime

class User(AbstractUser):
    verification_key = models.CharField(_('e-mail verification key'),
        max_length=256, null=True, editable=False)
    delete_deadline = models.DateTimeField(_('account deletion date'),
        null=True, db_index=True, editable=False)

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
