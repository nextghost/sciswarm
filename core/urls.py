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

from django.conf.urls import include, url
from django.contrib.auth import views as auth
from .views import account, comment, event, main, paper, user

account_patterns = [
    url(r'^login/?\Z', account.login, name='login'),
    url(r'^logout/?\Z', auth.logout, name='logout'),
    url(r'^register/?\Z', account.RegistrationView.as_view(),
        name='register'),
    url(r'^registered/?\Z', account.registration_complete, name='registered'),
    url(r'^edit_profile/?\Z', account.ProfileUpdateView.as_view(),
        name='edit_profile'),
    url(r'^add_identifier/?\Z', user.LinkPersonAliasView.as_view(),
        name='add_person_identifier'),
    url(r'^delete_identifier/(?P<pk>[0-9]+)/?\Z',
        user.UnlinkPersonAliasView.as_view(), name='unlink_person_identifier'),
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

person_patterns = [
    url(r'^(?P<username>[^/]+)/feed/?\Z', event.PersonEventFeed.as_view(),
        name='person_event_feed'),
    url(r'^(?P<username>[^/]+)/papers/?\Z',
        paper.PersonAuthoredPaperListView.as_view(),
        name='person_authored_paper_list'),
    url(r'^(?P<username>[^/]+)/posted_papers/?\Z',
        paper.PersonPostedPaperListView.as_view(),
        name='person_posted_paper_list'),
    url(r'^(?P<username>[^/]+)/?\Z', user.PersonDetailView.as_view(),
        name='person_detail'),
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
    url(r'^delete_link/(?P<pk>[0-9]+)/?\Z',
        paper.DeleteSupplementalLinkView.as_view(),
        name='delete_paper_supplemental_link'),
    url(r'^(?P<pk>[0-9]+)/cited_by/?\Z', paper.CitedByPaperListView.as_view(),
        name='cited_by_paper_list'),
    url(r'^(?P<pk>[0-9]+)/reviews/?\Z', comment.PaperReviewListView.as_view(),
        name='paperreview_list'),
    url(r'^(?P<pk>[0-9]+)/add_review/?\Z',
        comment.CreatePaperReviewView.as_view(), name='create_paperreview'),
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
    url(r'^(?P<pk>[0-9]+)/add_link/?\Z',
        paper.AddSupplementalLinkFormView.as_view(),
        name='add_paper_supplemental_link'),
    url(r'^(?P<paper>[0-9]+)/delete_citation/(?P<ref>[0-9]+)/?\Z',
        paper.DeleteCitationView.as_view(), name='delete_paper_citation'),
    url(r'^(?P<pk>[0-9]+)/?\Z', paper.PaperDetailView.as_view(),
        name='paper_detail'),
]

review_patterns = [
    url(r'^reply/(?P<pk>[0-9]+)/?\Z',
        comment.CreatePaperReviewResponseSubView.as_view(),
        name='create_paperreviewresponse_sub'),
    url(r'^edit_reply/(?P<pk>[0-9]+)/?\Z',
        comment.UpdatePaperReviewResponseView.as_view(),
        name='edit_paperreviewresponse'),
    url(r'^delete_reply/(?P<pk>[0-9]+)/?\Z',
        comment.DeletePaperReviewResponseView.as_view(),
        name='delete_paperreviewresponse'),
    url(r'^(?P<pk>[0-9]+)/reply/?\Z',
        comment.CreatePaperReviewResponseMainView.as_view(),
        name='create_paperreviewresponse_main'),
    url(r'^(?P<pk>[0-9]+)/edit/?\Z', comment.UpdatePaperReviewView.as_view(),
        name='edit_paperreview'),
    url(r'^(?P<pk>[0-9]+)/delete/?\Z', comment.DeletePaperReviewView.as_view(),
        name='delete_paperreview'),
    url(r'^(?P<pk>[0-9]+)/?\Z', comment.PaperReviewDetailView.as_view(),
        name='paperreview_detail'),
]

urlpatterns = [
    url(r'^\Z', main.homepage, name='homepage'),
    url(r'^p/?\Z', paper.PaperListView.as_view(), name='paper_list'),
    url(r'^u/', include(person_patterns)),
    url(r'^p/', include(paper_patterns)),
    url(r'^r/', include(review_patterns)),
    url(r'^account/', include(account_patterns)),
]
