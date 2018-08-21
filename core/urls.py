from django.conf.urls import include, url
from django.contrib.auth import views as auth
from .views import account, main

account_patterns = [
    url(r'^login/?\Z', account.login, name='login'),
    url(r'^logout/?\Z', auth.logout, name='logout'),
    url(r'^register/?\Z', account.RegistrationView.as_view(),
        name='register'),
    url(r'^edit_profile/?\Z', account.ProfileUpdateView.as_view(),
        name='edit_profile'),
    url(r'^change_password/?\Z', account.password_change,
        name='password_change'),
    url(r'^reset_password/?\Z', account.password_reset, name='password_reset'),
    url(r'^reset_started/?\Z', auth.password_reset_done,
        name='password_reset_done'),
    url(r'^finish_reset/?\Z', account.password_reset_confirm,
        name='password_reset_confirm'),
]

urlpatterns = [
    url(r'^\Z', main.homepage, name='homepage'),
    url(r'^account/', include(account_patterns)),
]
