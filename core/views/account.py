from django.conf import settings
from django.contrib.auth import views, REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import login_required
from django.db.transaction import atomic, on_commit
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.utils import translation
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from . import utils
from .base import BaseCreateView, BaseUpdateView
from ..forms.auth import (LoginForm, RegistrationForm, UserProfileUpdateForm,
    PasswordChangeForm, SetPasswordForm, DeleteAccountForm)
from ..utils.html import NavigationBar, full_reverse, query_string
from ..utils.mail import send_template_mail
from .. import models

@sensitive_post_parameters()
@csrf_protect
@never_cache
@atomic
def login(request):
    if request.user.is_authenticated:
        return utils.permission_denied(request)
    models.BruteBlock.objects.purge_stale()
    if models.BruteBlock.client_blocked(request):
        if request.POST:
            return HttpResponseRedirect(request.get_full_path())
        return render(request, 'core/account/tempblock.html', dict())
    nav_links = [(_('Lost password?'), 'core:password_reset', tuple(), dict())]
    context = dict(navbar=NavigationBar(request, nav_links))
    ret = views.login(request, authentication_form=LoginForm,
        extra_context=context)
    if request.user.is_authenticated:
        lang = request.user.language
        request.session[translation.LANGUAGE_SESSION_KEY] = lang
    return ret

@sensitive_post_parameters()
@csrf_protect
@never_cache
@login_required
def password_change(request):
    next_url = reverse('core:homepage')
    nav_links = [
        (_('Edit profile'), 'core:edit_profile', tuple(), dict()),
        (_('Delete account'), 'core:delete_account', tuple(), dict())
    ]
    context = dict(navbar=NavigationBar(request, nav_links))
    return views.password_change(request, post_change_redirect=next_url,
        password_change_form=PasswordChangeForm, extra_context=context)

def password_reset(request):
    if request.user.is_authenticated:
        return utils.permission_denied(request)
    email_tpl = 'core/email/password_reset'
    next_url = reverse('core:password_reset_done')
    email_context = dict(request=request)
    return views.password_reset(request, email_template_name=email_tpl+'.txt',
        subject_template_name=email_tpl+'_subject.txt',
        html_email_template_name=email_tpl+'.html',
        post_reset_redirect=next_url, extra_email_context=email_context)

def password_reset_confirm(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('core:homepage'))
    uid = request.GET.get('ref', '')
    token = request.GET.get('token', '')
    next_url = reverse('core:login')
    return views.password_reset_confirm(request, uid, token,
        set_password_form=SetPasswordForm, post_reset_redirect=next_url)

def verify_user_email(request):
    user_id = request.GET.get('ref')
    token = request.GET.get('token')
    if user_id is None:
        raise Http404()
    try:
        user_id = force_text(urlsafe_base64_decode(user_id))
        user = models.User.objects.get(pk=user_id)
    except:
        raise Http404()

    if user.verification_key is not None:
        if token is not None and token == user.verification_key:
            user.verification_key = None
            user.save(update_fields=['verification_key'])
        else:
            template = 'core/account/bad_verification_token.html'
            return render(request, template, dict())
    return HttpResponseRedirect(reverse('core:login'))

def registration_complete(request):
    return render(request, 'core/account/registered.html', dict())

@method_decorator(sensitive_post_parameters(), name='dispatch')
@method_decorator(atomic(), name='post')
class RegistrationView(BaseCreateView):
    template_name = 'core/account/register.html'
    form_class = RegistrationForm
    success_url = reverse_lazy('core:registered')

    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    @method_decorator(atomic)
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return utils.permission_denied(request)
        return super(RegistrationView, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        ret = super(RegistrationView, self).form_valid(form)
        def callback(request=self.request, form=form):
            template = 'core/email/registered'
            subject = _('Welcome to Sciswarm!')
            uid = urlsafe_base64_encode(force_bytes(form.instance.pk))
            verify_args = query_string(ref=uid,
                token=form.instance.verification_key)
            url = full_reverse(self.request, 'core:verify_user_email')
            context = dict(verify_url=''.join([url, '?', verify_args]))
            send_template_mail(self.request, subject, template, context,
                [form.instance.email])
        on_commit(callback)
        return ret

@method_decorator(sensitive_post_parameters(), name='dispatch')
@method_decorator(never_cache, name='dispatch')
@method_decorator(login_required, name='dispatch')
@method_decorator(atomic(), name='post')
class ProfileUpdateView(BaseUpdateView):
    template_name = 'core/account/profile_form.html'
    form_class = UserProfileUpdateForm
    success_url = reverse_lazy('core:homepage')
    page_title = _('Update User Profile')

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        nav_links = [
            (_('Edit profile'), 'core:edit_profile', tuple(), dict()),
            (_('Change password'), 'core:password_change', tuple(), dict()),
            (_('Delete account'), 'core:delete_account', tuple(), dict())
        ]
        context = super(ProfileUpdateView, self).get_context_data(**kwargs)
        context['navbar'] = NavigationBar(self.request, nav_links)
        return context

# Decorators applied in parent class
class DeleteAccountView(ProfileUpdateView):
    template_name = 'core/account/delete_form.html'
    form_class = DeleteAccountForm
    page_title = _('Delete Account')
