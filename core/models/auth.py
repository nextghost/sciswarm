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

    def filter_by_person(self, person):
        query = (self.model.query_model.person == person)
        return self.filter(query)

class User(auth_models.AbstractUser):
    class Meta:
        ordering = ('last_name', 'first_name')
    objects = UserManager()

    language = models.CharField(_('system language'), max_length=8)
    verification_key = models.CharField(_('e-mail verification key'),
        max_length=256, null=True, editable=False)
    delete_deadline = models.DateTimeField(_('account deletion date'),
        null=True, db_index=True, editable=False)
    person = models.ForeignKey('Person', verbose_name=_('person'),
        on_delete=models.PROTECT, related_name='+')

    def __str__(self):
        # This applies only to bots
        if (not self.first_name) or not self.last_name:
            return self.first_name or self.last_name
        args = dict(first_name=self.first_name, last_name=self.last_name)
        return _('{first_name} {last_name}').format(**args)

    @property
    def name(self):
        return str(self)

    def get_absolute_url(self):
        kwargs = dict(username=self.username)
        return reverse('core:person_detail', kwargs=kwargs)

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
