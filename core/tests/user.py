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

from django.core.exceptions import NON_FIELD_ERRORS
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from ..models import const
from .. import models

@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['sciswarm.test'])
class UserTestCase(TransactionTestCase):
    def test_authorship_acceptance(self):
        # Prepare test data
        partab = models.PaperAuthorReference.query_model
        sciswarm_scheme = const.person_alias_schemes.SCISWARM
        person_defaults = dict(title_before='', title_after='', bio='')
        user_defaults = dict(password='*', language='en', is_active=True,
            is_superuser=False)

        person1 = models.Person.objects.create(username='person1',
            first_name='Test', last_name='User1', **person_defaults)
        user1 = models.User.objects.create(username=person1.username,
            person=person1, **user_defaults)
        alias1 = models.PersonAlias.objects.create(scheme=sciswarm_scheme,
            identifier='u/' + person1.username, target=person1)
        person2 = models.Person.objects.create(username='person2',
            first_name='Test', last_name='User2', **person_defaults)
        user2 = models.User.objects.create(username=person2.username,
            person=person2, **user_defaults)
        alias2 = models.PersonAlias.objects.create(scheme=sciswarm_scheme,
            identifier='u/' + person2.username, target=person2)
        person3 = models.Person.objects.create(username='person3',
            first_name='Test', last_name='User3', **person_defaults)
        user3 = models.User.objects.create(username=person3.username,
            person=person3, **user_defaults)
        alias3 = models.PersonAlias.objects.create(scheme=sciswarm_scheme,
            identifier='u/' + person3.username, target=person3)

        paper_defaults = dict(abstract='Abstract', contents_theory=True,
            contents_survey=False, contents_observation=False,
            contents_experiment=False, contents_metaanalysis=False,
            year_published=2019)
        paper1 = models.Paper.objects.create(name='Paper1', posted_by=person1,
            changed_by=person1, **paper_defaults)
        paper2 = models.Paper.objects.create(name='Paper2', posted_by=person1,
            changed_by=person2, **paper_defaults)
        paper3 = models.Paper.objects.create(name='Paper3', posted_by=person2,
            changed_by=person2, **paper_defaults)
        paper4 = models.Paper.objects.create(name='Paper4', posted_by=person3,
            changed_by=person3, **paper_defaults)
        paper5 = models.Paper.objects.create(name='Paper5', posted_by=person2,
            changed_by=person3, **paper_defaults)
        paper6 = models.Paper.objects.create(name='Paper6', posted_by=person3,
            changed_by=person3, **paper_defaults)

        review_defaults = dict(message='Review',
            methodology=const.paper_quality_ratings.GOOD,
            importance=const.paper_importance_ratings.MEDIUM)
        models.PaperReview.objects.create(posted_by=person2, paper=paper1,
            **review_defaults)
        models.PaperReview.objects.create(posted_by=person3, paper=paper1,
            **review_defaults)
        models.PaperReview.objects.create(posted_by=person3, paper=paper3,
            **review_defaults)

        paper_list = [paper1, paper2, paper3, paper4, paper5]
        alias_list = [alias1, alias2, alias3]
        user_list = [user1, user2, user3]
        sciswarm_scheme = const.paper_alias_schemes.SCISWARM

        for paper in paper_list:
            models.PaperAlias.objects.create(scheme=sciswarm_scheme,
                identifier='p/' + str(paper.pk), target=paper)
            for alias in alias_list:
                models.PaperAuthorReference.objects.create(paper=paper,
                    author_alias=alias, confirmed=None)
        models.PaperAlias.objects.create(scheme=sciswarm_scheme,
            identifier='p/' + str(paper6.pk), target=paper6)

        c = Client(HTTP_HOST='sciswarm.test')

        # Test data: (user, accept/reject, (selected papers),
        # (expected confirmation status after test))
        test_data = [
            (user1, True, (paper1, paper2), (True, True, None, None, None)),
            (user1, False, (paper4, paper5), (True, True, None, False, False)),
            (user2, True, (paper1, paper3, paper5, paper6),
                (None, None, True, None, True)),
            # Paper 3 is already accepted, will be ignored
            (user2, False, (paper1, paper2, paper3, paper6),
                (None, False, True, None, True)),
            (user3, False, (paper1, paper2, paper3, paper4, paper6),
                (None, False, None, False, None)),
            # Paper 1 & 4 are already rejected, will be ignored
            (user3, True, (paper1, paper2, paper3, paper4, paper5, paper6),
                (None, False, None, False, True)),
        ]

        # Test mass acceptance/rejection
        fname_tpl = 'select_%d'
        url = reverse('core:mass_authorship_confirmation')
        for user, accept, plist, exp_status in test_data:
            post_data = dict(((fname_tpl % x.pk, True) for x in plist))
            action = '_confirm_authorship' if accept else '_reject_authorship'
            post_data[action] = 'Test'
            c.force_login(user)
            response = c.post(url, post_data)
            self.assertRedirects(response, url, fetch_redirect_response=False)
            exp_map = dict(zip((x.pk for x in paper_list), exp_status))
            query = (partab.author_alias.target == user.person)
            qs = models.PaperAuthorReference.objects.filter(query)
            tmp = [(x.pk, x.confirmed) for x in qs]
            for item in qs:
                self.assertIs(item.confirmed, exp_map[item.paper_id])

        test_data = [
            (user1, False, paper3),
            (user1, True, paper3),
            (user1, False, paper1),
            (user2, False, paper1),
            (user2, True, paper2),
            (user2, False, paper2),
            (user3, False, paper1),
            (user3, False, paper3),
        ]

        # Test successful authorship confirmation/rejection
        for user, accept, paper in test_data:
            kwargs = dict(pk=paper.pk)
            url = reverse('core:paper_authorship_confirmation', kwargs=kwargs)
            action = '_confirm_authorship' if accept else '_reject_authorship'
            post_data = {action: 'Test'}
            c.force_login(user)
            response = c.post(url, post_data)
            url = reverse('core:paper_detail', kwargs=kwargs)
            self.assertRedirects(response, url, fetch_redirect_response=False)
            query = ((partab.author_alias.target == user.person) &
                (partab.paper == paper))
            item = models.PaperAuthorReference.objects.get(query)
            self.assertIs(item.confirmed, accept)

        test_data = [
            (user2, True, paper1),
            (user3, True, paper1),
            (user3, True, paper3),
        ]

        # Test authorship confirmation error (blocked by review)
        for user, accept, paper in test_data:
            query = ((partab.author_alias.target == user.person) &
                (partab.paper == paper))
            testitem = models.PaperAuthorReference.objects.get(query)
            kwargs = dict(pk=paper.pk)
            url = reverse('core:paper_authorship_confirmation', kwargs=kwargs)
            action = '_confirm_authorship' if accept else '_reject_authorship'
            post_data = {action: 'Test'}
            c.force_login(user)
            response = c.post(url, post_data)
            url = reverse('core:paper_detail', kwargs=kwargs)
            self.assertEquals(response.status_code, 200)
            form = response.context['form']
            self.assertTrue(form.has_error(NON_FIELD_ERRORS, 'selfpromo'))
            query = ((partab.author_alias.target == user.person) &
                (partab.paper == paper))
            tmp = models.PaperAuthorReference.objects.get(query)
            self.assertIs(testitem.confirmed, tmp.confirmed)

        # Test attempt to confirm/reject non-existent authorship
        kwargs = dict(pk=paper6.pk)
        url = reverse('core:paper_authorship_confirmation', kwargs=kwargs)
        
        for user in user_list:
            post_data = {'_confirm_authorship': 'Test'}
            c.force_login(user)
            response = c.post(url, post_data)
            self.assertEquals(response.status_code, 404)

        self.assertFalse(paper6.paperauthorreference_set.exists())

        for user in user_list:
            post_data = {'_reject_authorship': 'Test'}
            c.force_login(user)
            response = c.post(url, post_data)
            self.assertEquals(response.status_code, 404)

        self.assertFalse(paper6.paperauthorreference_set.exists())
