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

from django.core.exceptions import NON_FIELD_ERRORS
from django.http import QueryDict
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from ..models import const
from .. import models

@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['sciswarm.test'])
class PaperTestCase(TransactionTestCase):
    def test_authorship_form(self):
        partab = models.PaperAuthorReference.query_model
        parobj = models.PaperAuthorReference.objects
        sciswarm_scheme = const.person_alias_schemes.SCISWARM
        orcid_scheme = const.person_alias_schemes.ORCID
        email_scheme = const.person_alias_schemes.EMAIL
        twitter_scheme = const.person_alias_schemes.TWITTER
        url_scheme = const.person_alias_schemes.URL
        other_scheme = const.person_alias_schemes.OTHER
        event_type = const.user_feed_events.AUTHORSHIP_CONFIRMED

        person_defaults = dict(title_before='', title_after='', bio='')
        user_defaults = dict(password='*', language='en', timezone='UTC',
            is_active=True, is_superuser=False)
        person1 = models.Person.objects.create(username='person1',
            first_name='Test', last_name='User1', **person_defaults)
        user1 = models.User.objects.create(username=person1.username,
            person=person1, email='permanent@example.com', **user_defaults)
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
        alias4 = models.PersonAlias.objects.create(scheme=email_scheme,
            identifier='person1@example.com', target=person1)
        alias5 = models.PersonAlias.objects.create(scheme=url_scheme,
            identifier='https://www.example.com/', target=person1)
        alias6 = models.PersonAlias.objects.create(scheme=orcid_scheme,
            identifier='0000-0002-1825-0097', target=person1)
        alias7 = models.PersonAlias.objects.create(scheme=email_scheme,
            identifier='anon@example.com', target=None)
        alias8 = models.PersonAlias.objects.create(scheme=email_scheme,
            identifier=user1.email, target=person1)

        paper_defaults = dict(abstract='Abstract', contents_theory=True,
            contents_survey=False, contents_observation=False,
            contents_experiment=False, contents_metaanalysis=False,
            year_published=2019)
        paper1 = models.Paper.objects.create(name='Paper1', posted_by=person2,
            changed_by=person1, **paper_defaults)
        paper2 = models.Paper.objects.create(name='Paper2', posted_by=person2,
            changed_by=person1, **paper_defaults)
        paper3 = models.Paper.objects.create(name='Paper3', posted_by=person2,
            changed_by=person1, **paper_defaults)
        paper4 = models.Paper.objects.create(name='Paper4', posted_by=person2,
            changed_by=person1, **paper_defaults)
        paper5 = models.Paper.objects.create(name='Paper5', posted_by=person2,
            changed_by=person1, **paper_defaults)

        authorship_list = [(alias1, paper1, True), (alias2, paper2, True),
            (alias4, paper2, True), (alias5, paper2, True),
            (alias2, paper3, True), (alias4, paper3, False),
            (alias2, paper4, None), (alias3, paper4, False),
            (alias4, paper4, True), (alias6, paper4, None),
            (alias7, paper4, None),
        ]
        event_set = set()

        for alias, paper, confirmed in authorship_list:
            parobj.create(paper=paper, author_alias=alias, confirmed=confirmed)
            if confirmed:
                event_set.add((alias.target, paper))

        for person, paper in event_set:
            models.FeedEvent.objects.create(person=person, paper=paper,
                event_type=event_type)

        par_count = parobj.count()
        alias_count = models.PersonAlias.objects.count()

        c = Client(HTTP_HOST='sciswarm.test')
        c.force_login(user2)

        test_data = [
            (email_scheme, 'fnord@example.com', dict()),
            (orcid_scheme, '0000-0002-9079-593X', dict()),
            (twitter_scheme, '@TwitterAPI', dict()),
            (url_scheme, 'https://other.example.com/',
                dict(scheme=other_scheme)),
            (email_scheme, 'test@example.com', dict(scheme=other_scheme,
                identifier='mailto:test@example.com')),
            # Generic identifier
            ('foo', 'bar', dict(scheme=other_scheme, identifier='foo:bar')),
        ]

        # Test adding unlinked authors
        url = reverse('core:add_paper_author', kwargs=dict(pk=paper5.pk))
        redir_url = reverse('core:paper_detail', kwargs=dict(pk=paper5.pk))
        for scheme, identifier, override in test_data:
            post_data = dict(scheme=scheme, identifier=identifier)
            post_data.update(override)
            response = c.post(url, post_data)
            self.assertRedirects(response, redir_url,
                fetch_redirect_response=False)
            qs = paper5.paperauthorreference_set.order_by('-pk')
            tmp = qs.select_related('author_alias').first()
            self.assertIsNot(tmp, None)
            self.assertEqual(tmp.author_alias.scheme, scheme)
            self.assertEqual(tmp.author_alias.identifier, identifier)
            self.assertIs(tmp.author_alias.target_id, None)
            self.assertIs(tmp.confirmed, None)

        qs = paper5.paperauthorreference_set
        self.assertEqual(qs.count(), len(test_data))

        test_data = [
            (paper2, alias3, dict()),
            (paper4, alias1, dict(scheme=other_scheme,
                identifier=alias1.scheme + ':' + alias1.identifier)),
            (paper3, alias7, dict()),
            (paper5, alias3, dict()),
        ]

        # Test adding linked authors
        for paper, alias, override in test_data:
            url = reverse('core:add_paper_author', kwargs=dict(pk=paper.pk))
            post_data = dict(scheme=alias.scheme, identifier=alias.identifier)
            post_data.update(override)
            response = c.post(url, post_data)
            redir_url = reverse('core:paper_detail', kwargs=dict(pk=paper.pk))
            self.assertRedirects(response, redir_url,
                fetch_redirect_response=False)
            qs = paper.paperauthorreference_set.order_by('-pk')
            tmp = qs.select_related('author_alias__target').first()
            self.assertIsNot(tmp, None)
            self.assertEqual(tmp.author_alias, alias)
            self.assertEqual(tmp.author_alias.scheme, alias.scheme)
            self.assertEqual(tmp.author_alias.identifier, alias.identifier)
            self.assertEqual(tmp.author_alias.target, alias.target)
            self.assertIs(tmp.confirmed, None)

        # Test that adding the same alias again is a no-op success
        url = reverse('core:add_paper_author', kwargs=dict(pk=paper2.pk))
        post_data = dict(scheme=alias4.scheme, identifier=alias4.identifier)
        post_data.update(override)
        response = c.post(url, post_data)
        redir_url = reverse('core:paper_detail', kwargs=dict(pk=paper2.pk))
        self.assertRedirects(response, redir_url,
            fetch_redirect_response=False)
        query = ((partab.paper == paper2) & (partab.author_alias == alias4))
        qs = paper2.paperauthorreference_set.filter(query)
        tmp = qs.select_related('author_alias__target').get()
        self.assertEqual(tmp.author_alias, alias4)
        self.assertEqual(tmp.author_alias.scheme, alias4.scheme)
        self.assertEqual(tmp.author_alias.identifier, alias4.identifier)
        self.assertEqual(tmp.author_alias.target, alias4.target)
        self.assertIs(tmp.confirmed, True)

        test_data = [
            (email_scheme, 'foo', 'invalid'),
            (orcid_scheme, 'foo', 'invalid'),
            (twitter_scheme, 'foo', 'invalid'),
            (sciswarm_scheme, 'foo', 'invalid'),
            (sciswarm_scheme, 'u/test', 'invalid'),
            (url_scheme, 'foo', 'invalid'),
            (other_scheme, 'foo', 'invalid'),
            (other_scheme, 'abcdefghijklmnopq:foo', 'max_length'),
            (alias1.scheme, alias1.identifier, 'rejected'),
        ]

        # Test form error checks
        alias_count = models.PersonAlias.objects.count()
        par_count = parobj.count()

        for scheme, identifier, code in test_data:
            url = reverse('core:add_paper_author', kwargs=dict(pk=paper3.pk))
            post_data = dict(scheme=scheme, identifier=identifier)
            response = c.post(url, post_data)
            self.assertEqual(response.status_code, 200)
            form = response.context['form']
            self.assertTrue(form.has_error('identifier', code), post_data)
            self.assertEqual(models.PersonAlias.objects.count(), alias_count)
            self.assertEqual(parobj.count(), par_count)

        # Test that non-author cannot add authors to papers with linked authors
        for paper in [paper1, paper5]:
            url = reverse('core:add_paper_author', kwargs=dict(pk=paper5.pk))
            post_data = dict(scheme=scheme, identifier=identifier)
            response = c.post(url, post_data)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(models.PersonAlias.objects.count(), alias_count)
            self.assertEqual(parobj.count(), par_count)

        test_data = [
            (paper4, alias4, True),
            (paper2, alias4, False),
            (paper2, alias5, True),
            (paper4, alias6, False),
        ]

        # Test deleting authors
        for paper, alias, del_event in test_data:
            exp_ref = models.PaperAuthorReference.objects.in_bulk()
            query = (partab.author_alias == alias)
            ref = paper.paperauthorreference_set.get(query)
            url = reverse('core:delete_paper_author', kwargs=dict(pk=ref.pk))
            response = c.post(url, dict())
            redir_url = reverse('core:paper_detail', kwargs=dict(pk=paper.pk))
            self.assertRedirects(response, redir_url,
                fetch_redirect_response=False)
            del exp_ref[ref.pk]
            check_map = models.PaperAuthorReference.objects.in_bulk()
            for exp in exp_ref.values():
                item = check_map[exp.pk]
                self.assertEqual(item.paper_id, exp.paper_id)
                self.assertEqual(item.author_alias_id, exp.author_alias_id)
                self.assertIs(item.confirmed, exp.confirmed)
            if del_event:
                event_set.discard((alias.target, paper))
            query = (models.FeedEvent.query_model.event_type == event_type)
            qs = models.FeedEvent.objects.filter(query)
            qs = qs.select_related('person', 'paper')
            self.assertEqual(len(qs), len(event_set))
            test_set = set(((x.person, x.paper) for x in qs))
            self.assertEqual(test_set, event_set)

        test_data = [
            (paper3, alias4),
            (paper1, alias1),
            (paper5, alias3),
        ]

        # Test that rejected authorships cannot be deleted
        # Test that non-author cannot delete authors of papers with linked
        # authors
        alias_count = models.PersonAlias.objects.count()
        par_count = parobj.count()

        for paper, alias in test_data:
            exp_ref = models.PaperAuthorReference.objects.in_bulk()
            query = (partab.author_alias == alias)
            ref = paper.paperauthorreference_set.get(query)
            url = reverse('core:delete_paper_author', kwargs=dict(pk=ref.pk))
            response = c.post(url, dict())
            self.assertEqual(response.status_code, 403)
            check_map = models.PaperAuthorReference.objects.in_bulk()
            for exp in exp_ref.values():
                item = check_map[exp.pk]
                self.assertEqual(item.paper_id, exp.paper_id)
                self.assertEqual(item.author_alias_id, exp.author_alias_id)
                self.assertIs(item.confirmed, exp.confirmed)
            query = (models.FeedEvent.query_model.event_type == event_type)
            qs = models.FeedEvent.objects.filter(query)
            qs = qs.select_related('person', 'paper')
            self.assertEqual(len(qs), len(event_set))
            test_set = set(((x.person, x.paper) for x in qs))
            self.assertEqual(test_set, event_set)
            self.assertEqual(models.PersonAlias.objects.count(), alias_count)
            self.assertEqual(parobj.count(), par_count)
