from django.conf import settings
from django.contrib.auth import forms as auth
from django.forms import ValidationError
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone, translation
from django import forms
from .base import HelpTextMixin, ModelForm
from .. import models
from ..models import const
from ..utils.utils import generate_token
import datetime
import re

class LoginForm(auth.AuthenticationForm):
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        if username and models.BruteBlock.username_blocked(username):
            msg = _('This account has been temporarily blocked due to high number of login failures. Please try again later.')
            raise ValidationError(msg, code='temporary_block')
        try:
            return super(LoginForm, self).clean()
        except ValidationError:
            models.BruteBlock.login_failure(self.request, username)
            raise

    def confirm_login_allowed(self, user):
        super(LoginForm, self).confirm_login_allowed(user)
        if user.verification_key is not None:
            msg = _('You need to verify your e-mail address before first login. If you have not received the verification e-mail, please contact the administrator.')
            raise ValidationError(msg, 'verification_pending')
        if user.delete_deadline is not None:
            msg = _('Your account is set to be deleted soon. If you have changed your mind, please contact the administrator.')
            raise ValidationError(msg, 'delete_pending')

class RegistrationForm(HelpTextMixin, auth.UserCreationForm):
    class Meta(auth.UserCreationForm.Meta):
        model = models.User
        fields = ['username', 'password1', 'password2', 'email',
            'title_before', 'first_name', 'last_name', 'title_after',
            'language', 'bio']
        help_texts = {'username': _('Required. 150 characters or fewer. Lowercase English letters, digits and @/./+/-/_ only.')}
        error_messages = {
            'username': {'invalid': _('This username is not allowed. Username may contain only lowercase English letters, numbers, and @/./+/-/_ characters.')}
        }
    language = forms.ChoiceField(label=_('Language'),
        choices=settings.LANGUAGES)

    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        self.initial.setdefault('language', translation.get_language())

    def clean(self):
        super(RegistrationForm, self).clean()
        email = self.cleaned_data.get('email')
        username = self.cleaned_data.get('username')
        if email is not None:
            aliasobj = models.UserAlias.objects
            scheme = const.person_alias_schemes.EMAIL
            if not aliasobj.check_alias_available(scheme, email):
                msg = _('This e-mail address is already taken.')
                err = ValidationError(msg, 'unique')
                self.add_error('email', err)
        if username is not None and not re.match(r'^[a-z0-9@.+_-]+$',username):
            msg = _('This username is not allowed.')
            err = ValidationError(msg, 'invalid')
            self.add_error('username', err)

    def save(self, commit=True):
        self.instance.verification_key = generate_token(32)
        ret = super(RegistrationForm, self).save(commit)
        scheme = const.person_alias_schemes.EMAIL
        models.UserAlias.objects.link_alias(scheme, ret.email, ret)
        scheme = const.person_alias_schemes.SCISWARM
        models.UserAlias.objects.link_alias(scheme, 'u/' + ret.username, ret)
        return ret

class UserProfileUpdateForm(ModelForm):
    class Meta:
        model = models.User
        fields = ['password_check', 'email', 'title_before', 'first_name',
            'last_name', 'title_after', 'language', 'bio']
    language = forms.ChoiceField(label=_('Language'),
        choices=settings.LANGUAGES)
    password_check = forms.CharField(label=_('Password'),
        widget=forms.PasswordInput)

    def clean_password_check(self):
        pwd = self.cleaned_data.get('password_check', '')
        if not self.instance.check_password(pwd):
            raise ValidationError(_('Wrong password.'), code='bad_password')
        return pwd

    def clean(self):
        email = self.cleaned_data.get('email')
        if email is not None and 'email' in self.changed_data:
            aliasobj = models.UserAlias.objects
            scheme = const.person_alias_schemes.EMAIL
            if not aliasobj.check_alias_available(scheme,email, self.instance):
                msg = _('This e-mail address is already taken.')
                err = ValidationError(msg, 'unique')
                self.add_error('email', err)

    def save(self, commit=True):
        ret = super(UserProfileUpdateForm, self).save(commit)
        if 'email' in self.changed_data:
            scheme = const.person_alias_schemes.EMAIL
            models.UserAlias.objects.link_alias(scheme, ret.email, ret)
        return ret

class DeleteAccountForm(ModelForm):
    class Meta:
        model = models.User
        fields = []
    password_check = forms.CharField(label=_('Password'),
        widget=forms.PasswordInput)

    def clean_password_check(self):
        pwd = self.cleaned_data.get('password_check', '')
        if not self.instance.check_password(pwd):
            raise ValidationError(_('Wrong password.'), code='bad_password')
        return pwd

    def save(self, commit=True):
        delta = datetime.timedelta(days=30)
        self.instance.delete_deadline = timezone.now() + delta
        return super(DeleteAccountForm, self).save(commit)

class SetPasswordForm(auth.SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super(SetPasswordForm, self).__init__(*args, **kwargs)
        self.fields['new_password1'].help_text = ''

class PasswordChangeForm(auth.PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super(PasswordChangeForm, self).__init__(*args, **kwargs)
        self.fields['new_password1'].help_text = ''
