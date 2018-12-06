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

from django.conf.urls import include, url
from django.contrib.auth import views as auth
from .views import account, main, paper, user

account_patterns = [
    url(r'^login/?\Z', account.login, name='login'),
    url(r'^logout/?\Z', auth.logout, name='logout'),
    url(r'^register/?\Z', account.RegistrationView.as_view(),
        name='register'),
    url(r'^registered/?\Z', account.registration_complete, name='registered'),
    url(r'^edit_profile/?\Z', account.ProfileUpdateView.as_view(),
        name='edit_profile'),
    url(r'^add_identifier/?\Z', user.LinkUserAliasView.as_view(),
        name='add_user_identifier'),
    url(r'^delete_identifier/(?P<pk>[0-9]+)/?\Z',
        user.UnlinkUserAliasView.as_view(), name='unlink_user_identifier'),
    url(r'^manage_authorship/?\Z',
        user.MassAuthorshipConfirmationView.as_view(),
        name='mass_authorship_confirmation'),
    url(r'^rejected_papers/?\Z',
        paper.RejectedAuthorshipPaperListView.as_view(),
        name='rejected_authorship_paper_list'),
    url(r'^change_password/?\Z', account.password_change,
        name='password_change'),
    url(r'^reset_password/?\Z', account.password_reset, name='password_reset'),
    url(r'^reset_started/?\Z', auth.password_reset_done,
        name='password_reset_done'),
    url(r'^finish_reset/?\Z', account.password_reset_confirm,
        name='password_reset_confirm'),
    url(r'^verify_email/?\Z', account.verify_user_email,
        name='verify_user_email'),
    url(r'^delete/?\Z', account.DeleteAccountView.as_view(),
        name='delete_account'),
]

user_patterns = [
    url(r'^(?P<username>[^/]+)/papers/?\Z',
        paper.UserAuthoredPaperListView.as_view(),
        name='user_authored_paper_list'),
    url(r'^(?P<username>[^/]+)/posted_papers/?\Z',
        paper.UserPostedPaperListView.as_view(),
        name='user_posted_paper_list'),
    url(r'^(?P<username>[^/]+)/?\Z', user.UserDetailView.as_view(),
        name='user_detail'),
]

paper_patterns = [
    url(r'^new/?\Z', paper.CreatePaperView.as_view(), name='create_paper'),
    url(r'^delete_identifier/(?P<pk>[0-9]+)/?\Z',
        paper.UnlinkPaperAliasView.as_view(), name='unlink_paper_identifier'),
    url(r'^delete_author/(?P<pk>[0-9]+)/?\Z',
        paper.DeletePaperAuthorView.as_view(), name='delete_paper_author'),
    url(r'^delete_author_name/(?P<pk>[0-9]+)/?\Z',
        paper.DeletePaperAuthorNameView.as_view(),
        name='delete_paper_author_name'),
    url(r'^(?P<pk>[0-9]+)/cited_by/?\Z', paper.CitedByPaperListView.as_view(),
        name='cited_by_paper_list'),
    url(r'^(?P<pk>[0-9]+)/edit/?\Z', paper.UpdatePaperView.as_view(),
        name='edit_paper'),
    url(r'^(?P<pk>[0-9]+)/add_author/?\Z',
        paper.AddPaperAuthorView.as_view(), name='add_paper_author'),
    url(r'^(?P<pk>[0-9]+)/manage_authorship/?\Z',
        paper.PaperAuthorshipConfirmationView.as_view(),
        name='paper_authorship_confirmation'),
    url(r'^(?P<pk>[0-9]+)/add_identifier/?\Z',
        paper.LinkPaperAliasView.as_view(), name='add_paper_identifier'),
    url(r'^(?P<pk>[0-9]+)/add_citations/?\Z',
        paper.AddCitationsFormView.as_view(), name='add_paper_citations'),
    url(r'^(?P<paper>[0-9]+)/delete_citation/(?P<ref>[0-9]+)/?\Z',
        paper.DeleteCitationView.as_view(), name='delete_paper_citation'),
    url(r'^(?P<pk>[0-9]+)/?\Z', paper.PaperDetailView.as_view(),
        name='paper_detail'),
]

urlpatterns = [
    url(r'^\Z', main.homepage, name='homepage'),
    url(r'^p/?\Z', paper.PaperListView.as_view(), name='paper_list'),
    url(r'^u/', include(user_patterns)),
    url(r'^p/', include(paper_patterns)),
    url(r'^account/', include(account_patterns)),
]
