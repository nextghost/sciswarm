from django.contrib.auth import forms as auth
from django.forms import ValidationError
from django.utils.translation import ugettext_lazy as _, ugettext_noop
from django import forms
from .base import HelpTextMixin, ModelForm
from .. import models

# FIXME: Fix upstream translation and remove this
ugettext_noop(
    'Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.')
ugettext_noop(
    'Enter a valid username. This value may contain only English letters, '
    'numbers, and @/./+/-/_ characters.')
ugettext_noop(
    'Enter a valid username. This value may contain only letters, '
    'numbers, and @/./+/-/_ characters.')

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

class RegistrationForm(HelpTextMixin, auth.UserCreationForm):
    class Meta(auth.UserCreationForm.Meta):
        model = models.User
        fields = ['username', 'password1', 'password2', 'email', 'first_name',
            'last_name']

class UserProfileUpdateForm(ModelForm):
    class Meta:
        model = models.User
        fields = ['email', 'first_name', 'last_name', 'password_check']
    password_check = forms.CharField(label=_('Password'),
        widget=forms.PasswordInput)

    def clean_password_check(self):
        pwd = self.cleaned_data.get('password_check', '')
        if not self.instance.check_password(pwd):
            raise ValidationError(_('Wrong password.'), code='bad_password')
        return pwd

class SetPasswordForm(auth.SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super(SetPasswordForm, self).__init__(*args, **kwargs)
        self.fields['new_password1'].help_text = ''

class PasswordChangeForm(auth.PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super(PasswordChangeForm, self).__init__(*args, **kwargs)
        self.fields['new_password1'].help_text = ''
