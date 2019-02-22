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
class UserTestCase(TransactionTestCase):
    def test_useralias_linking(self):
        aliastab = models.PersonAlias.query_model
        aliasobj = models.PersonAlias.objects
        partab = models.PaperAuthorReference.query_model
        parobj = models.PaperAuthorReference.objects
        sciswarm_scheme = const.person_alias_schemes.SCISWARM
        orcid_scheme = const.person_alias_schemes.ORCID
        email_scheme = const.person_alias_schemes.EMAIL
        twitter_scheme = const.person_alias_schemes.TWITTER
        url_scheme = const.person_alias_schemes.URL
        other_scheme = const.person_alias_schemes.OTHER

        person_defaults = dict(title_before='', title_after='', bio='')
        user_defaults = dict(password='*', language='en', timezone='UTC',
            is_active=True, is_superuser=False)
        person1 = models.Person.objects.create(username='person1',
            first_name='Test', last_name='User1', **person_defaults)
        user1 = models.User.objects.create(username=person1.username,
            person=person1, **user_defaults)
        alias1 = models.PersonAlias.objects.create(scheme=sciswarm_scheme,
            identifier=person1.base_identifier, target=person1)
        person2 = models.Person.objects.create(username='person2',
            first_name='Test', last_name='User2', **person_defaults)
        user2 = models.User.objects.create(username=person2.username,
            person=person2, **user_defaults)
        alias2 = models.PersonAlias.objects.create(scheme=sciswarm_scheme,
            identifier=person2.base_identifier, target=person2)
        person3 = models.Person.objects.create(username='person3',
            first_name='Test', last_name='User3', **person_defaults)
        user3 = models.User.objects.create(username=person3.username,
            person=person3, **user_defaults)
        alias3 = models.PersonAlias.objects.create(scheme=sciswarm_scheme,
            identifier=person3.base_identifier, target=person3)

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

        review_defaults = dict(message='Review',
            methodology=const.paper_quality_ratings.GOOD,
            importance=const.paper_importance_ratings.MEDIUM)
        models.PaperReview.objects.create(posted_by=person2, paper=paper1,
            **review_defaults)
        # Deleted review must not affect authorship acceptance
        models.PaperReview.objects.create(posted_by=person2, paper=paper4,
            deleted=True, **review_defaults)
        models.PaperReview.objects.create(posted_by=person3, paper=paper1,
            **review_defaults)
        models.PaperReview.objects.create(posted_by=person3, paper=paper3,
            **review_defaults)

        paper_list = [paper1, paper2, paper3, paper4]
        alias_list = [alias1, alias2, alias3]
        user_list = [user1, user2, user3]
        sciswarm_scheme = const.paper_alias_schemes.SCISWARM

        for paper in paper_list:
            models.PaperAlias.objects.create(scheme=sciswarm_scheme,
                identifier='p/' + str(paper.pk), target=paper)

        author_list = [
            (paper1, email_scheme, 'foo@example.com'), # person2
            (paper1, orcid_scheme, '0000-0002-1825-0097'),
            (paper1, url_scheme, 'https://example.com/'), # person3
            (paper2, twitter_scheme, '@twitter'),
            (paper2, email_scheme, 'bar@example.com'),
            (paper2, email_scheme, 'foo@example.com'),
            (paper3, url_scheme, 'https://example.com/'),
            (paper4, email_scheme, 'baz@example.com'),
            (paper4, email_scheme, 'foo@example.com'),
        ]

        for paper, scheme, ident in author_list:
            tmp = models.PersonAlias.objects.create_alias(scheme, ident)
            models.PaperAuthorReference.objects.create(paper=paper,
                author_alias=tmp, confirmed=None)

        models.PersonAlias.objects.create_alias('foo', 'baz')

        c = Client(HTTP_HOST='sciswarm.test')

        test_data = [
            (user1, email_scheme, 'fnord@example.com', dict()),
            (user1, orcid_scheme, '0000-0002-9079-593X', dict()),
            (user2, twitter_scheme, '@TwitterAPI', dict()),
            (user2, url_scheme, 'https://www.swarmtech.cz/',
                dict(scheme=other_scheme)),
            (user2, email_scheme, 'test@example.com', dict(scheme=other_scheme,
                identifier='mailto:test@example.com')),
            # Generic identifier
            (user3, 'foo', 'bar', dict(scheme=other_scheme,
                identifier='foo:bar')),
        ]

        url = reverse('core:add_person_identifier')
        par_count = parobj.count()
        alias_count = models.PersonAlias.objects.count()

        # Test that anonymous user cannot create aliases
        post_data = dict(scheme=email_scheme, identifier='anon@example.com')
        response = c.post(url, post_data)
        args = QueryDict(mutable=True)
        args['next'] = url
        redir_url = reverse('core:login') + '?' + args.urlencode(safe='/')
        self.assertRedirects(response, redir_url,fetch_redirect_response=False)
        self.assertEqual(parobj.count(), par_count)
        self.assertEqual(models.PersonAlias.objects.count(), alias_count)
        query = partab.confirmed.notnull()
        self.assertFalse(parobj.filter(query).exists())

        # Test creation of new aliases
        for user, scheme, ident, override in test_data:
            post_data = dict(scheme=scheme, identifier=ident)
            post_data.update(override)
            c.force_login(user)
            response = c.post(url, post_data)
            redir_url = user.person.get_absolute_url()
            self.assertRedirects(response, redir_url,
                fetch_redirect_response=False)
            query = ((aliastab.scheme == scheme) &
                (aliastab.identifier == ident))
            tmp = aliasobj.get(query)
            self.assertEqual(tmp.target, user.person)
            self.assertEqual(parobj.count(), par_count)
            query = partab.confirmed.notnull()
            self.assertFalse(parobj.filter(query).exists())

        test_data = [
            (user2, email_scheme, 'foo@example.com', dict(), {paper1.pk: False,
                paper2.pk: None, paper4.pk: None}),
            (user1, orcid_scheme, '0000-0002-1825-0097',
                dict(scheme=other_scheme,
                identifier='ORCID:0000-0002-1825-0097'),
                {paper1.pk: None}),
            # Duplicate alias should be silently ignored
            (user1, orcid_scheme, '0000-0002-1825-0097', dict(),
                {paper1.pk: None}),
            (user3, twitter_scheme, '@twitter', dict(), {paper2.pk: None}),
            (user3, url_scheme, 'https://example.com/', dict(),
                {paper1.pk: False, paper3.pk: False}),
            (user2, 'foo', 'baz', dict(scheme=other_scheme,
                identifier='foo:baz'), dict()),
        ]

        # Test linking of existing unlinked aliases
        for user, scheme, ident, override, exp_authorship in test_data:
            post_data = dict(scheme=scheme, identifier=ident)
            post_data.update(override)
            c.force_login(user)
            response = c.post(url, post_data)
            redir_url = user.person.get_absolute_url()
            self.assertRedirects(response, redir_url,
                fetch_redirect_response=False)
            query = ((aliastab.scheme == scheme) &
                (aliastab.identifier == ident))
            tmp = aliasobj.get(query)
            self.assertEqual(tmp.target, user.person)
            self.assertEqual(parobj.count(), par_count)
            qs = tmp.paperauthorreference_set.all()
            authorship = dict(((x.paper_id, x.confirmed) for x in qs))
            self.assertEqual(authorship, exp_authorship)

        test_data = [
            (email_scheme, 'foo', 'invalid'),
            (orcid_scheme, 'foo', 'invalid'),
            (twitter_scheme, 'foo', 'invalid'),
            (sciswarm_scheme, 'foo', 'invalid'),
            (sciswarm_scheme, 'u/test', 'invalid'),
            (url_scheme, 'foo', 'invalid'),
            (other_scheme, 'foo', 'invalid'),
            (other_scheme, 'abcdefghijklmnopq:foo', 'max_length'),
            # Already assigned to user2
            (email_scheme, 'test@example.com', 'unique'),
        ]

        c.force_login(user1)
        alias_count = models.PersonAlias.objects.count()

        # Test form error checks
        for scheme, ident, code in test_data:
            post_data = dict(scheme=scheme, identifier=ident)
            response = c.post(url, post_data)
            self.assertEqual(response.status_code, 200)
            form = response.context['form']
            self.assertTrue(form.has_error('identifier', code))
            self.assertEqual(models.PersonAlias.objects.count(), alias_count)
            self.assertEqual(parobj.count(), par_count)
            query = partab.confirmed.notnull()
            self.assertEqual(parobj.filter(query).count(), 3)

    def test_useralias_unlinking(self):
        partab = models.PaperAuthorReference.query_model
        parobj = models.PaperAuthorReference.objects
        sciswarm_scheme = const.person_alias_schemes.SCISWARM
        orcid_scheme = const.person_alias_schemes.ORCID
        email_scheme = const.person_alias_schemes.EMAIL
        url_scheme = const.person_alias_schemes.URL
        event_type = const.user_feed_events.AUTHORSHIP_CONFIRMED

        person_defaults = dict(title_before='', title_after='', bio='')
        user_defaults = dict(password='*', language='en', timezone='UTC',
            is_active=True, is_superuser=False)
        person1 = models.Person.objects.create(username='person1',
            first_name='Test', last_name='User1', **person_defaults)
        user1 = models.User.objects.create(username=person1.username,
            person=person1, email='permanent@example.com', **user_defaults)
        alias1 = models.PersonAlias.objects.create(scheme=sciswarm_scheme,
            identifier=person1.base_identifier, target=person1)
        person2 = models.Person.objects.create(username='person2',
            first_name='Test', last_name='User2', **person_defaults)
        alias2 = models.PersonAlias.objects.create(scheme=sciswarm_scheme,
            identifier=person2.base_identifier, target=person2)
        alias3 = models.PersonAlias.objects.create(scheme=email_scheme,
            identifier='person1@example.com', target=person1)
        alias4 = models.PersonAlias.objects.create(scheme=url_scheme,
            identifier='https://www.example.com/', target=person1)
        alias5 = models.PersonAlias.objects.create(scheme=orcid_scheme,
            identifier='0000-0002-1825-0097', target=person1)
        alias6 = models.PersonAlias.objects.create(scheme=email_scheme,
            identifier='anon@example.com', target=None)
        alias7 = models.PersonAlias.objects.create(scheme=email_scheme,
            identifier=user1.email, target=person1)

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
        paper4 = models.Paper.objects.create(name='Paper4', posted_by=person2,
            changed_by=person1, **paper_defaults)

        authorship_list = [(alias1, paper1, True), (alias2, paper2, True),
            (alias3, paper2, True), (alias4, paper2, True),
            (alias6, paper2, None), (alias2, paper3, True),
            (alias3, paper3, False), (alias2, paper4, False),
            (alias3, paper4, True), (alias5, paper4, None),
            (alias6, paper4, None),
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
        c.force_login(user1)

        # Test unlinking of an alias
        kwargs = dict(pk=alias3.pk)
        url = reverse('core:unlink_person_identifier', kwargs=kwargs)
        kwargs = dict(username=person1.username)
        redir_url = reverse('core:person_detail', kwargs=kwargs)
        response = c.post(url, dict())
        self.assertRedirects(response, redir_url,fetch_redirect_response=False)
        tmp = models.PersonAlias.objects.get(pk=alias3.pk)
        self.assertEqual(tmp.scheme, alias3.scheme)
        self.assertEqual(tmp.identifier, alias3.identifier)
        self.assertIs(tmp.target_id, None)
        self.assertEqual(models.PersonAlias.objects.count(), alias_count)
        self.assertEqual(tmp.paperauthorreference_set.count(), 3)
        par_list = list(parobj.order_by('pk'))
        self.assertEqual(len(par_list), par_count)
        for item, exp in zip(par_list, authorship_list):
            self.assertEqual(item.author_alias_id, exp[0].pk)
            self.assertEqual(item.paper_id, exp[1].pk)
            if item.author_alias_id == tmp.pk:
                self.assertIs(item.confirmed, None)
            else:
                self.assertIs(item.confirmed, exp[2])
        event_set.discard((person1, paper4))
        query = (models.FeedEvent.query_model.event_type == event_type)
        qs = models.FeedEvent.objects.filter(query)
        qs = qs.select_related('person', 'paper')
        self.assertEqual(len(qs), len(event_set))
        test_set = set(((x.person, x.paper) for x in qs))
        self.assertEqual(test_set, event_set)

        # Test deletion of authorship confirmation events
        kwargs = dict(pk=alias4.pk)
        url = reverse('core:unlink_person_identifier', kwargs=kwargs)
        kwargs = dict(username=person1.username)
        redir_url = reverse('core:person_detail', kwargs=kwargs)
        response = c.post(url, dict())
        self.assertRedirects(response, redir_url,fetch_redirect_response=False)
        tmp = models.PersonAlias.objects.get(pk=alias4.pk)
        self.assertEqual(tmp.scheme, alias4.scheme)
        self.assertEqual(tmp.identifier, alias4.identifier)
        self.assertIs(tmp.target_id, None)
        self.assertEqual(models.PersonAlias.objects.count(), alias_count)
        self.assertEqual(tmp.paperauthorreference_set.count(), 1)
        par_list = list(parobj.order_by('pk'))
        self.assertEqual(len(par_list), par_count)
        for item, exp in zip(par_list, authorship_list):
            self.assertEqual(item.author_alias_id, exp[0].pk)
            self.assertEqual(item.paper_id, exp[1].pk)
            if item.author_alias_id in [alias3.pk, alias4.pk]:
                self.assertIs(item.confirmed, None)
            else:
                self.assertIs(item.confirmed, exp[2])
        event_set.discard((person1, paper2))
        query = (models.FeedEvent.query_model.event_type == event_type)
        qs = models.FeedEvent.objects.filter(query)
        qs = qs.select_related('person', 'paper')
        self.assertEqual(len(qs), len(event_set))
        test_set = set(((x.person, x.paper) for x in qs))
        self.assertEqual(test_set, event_set)

        # Test that permanent aliases cannot be unlinked
        kwargs = dict(pk=alias1.pk)
        url = reverse('core:unlink_person_identifier', kwargs=kwargs)
        kwargs = dict(username=person1.username)
        response = c.post(url, dict())
        self.assertEqual(response.status_code, 403)
        tmp = models.PersonAlias.objects.get(pk=alias1.pk)
        self.assertEqual(tmp.scheme, alias1.scheme)
        self.assertEqual(tmp.identifier, alias1.identifier)
        self.assertIs(tmp.target_id, alias1.target_id)

        # Test that users cannot unlink somebody else's alias
        for alias in [alias2, alias6]:
            kwargs = dict(pk=alias.pk)
            url = reverse('core:unlink_person_identifier', kwargs=kwargs)
            kwargs = dict(username=person1.username)
            response = c.post(url, dict())
            self.assertEqual(response.status_code, 404)
            tmp = models.PersonAlias.objects.get(pk=alias.pk)
            self.assertEqual(tmp.scheme, alias.scheme)
            self.assertEqual(tmp.identifier, alias.identifier)
            self.assertIs(tmp.target_id, alias.target_id)

        self.assertEqual(models.PersonAlias.objects.count(), alias_count)
        par_list = list(parobj.order_by('pk'))
        self.assertEqual(len(par_list), par_count)
        for item, exp in zip(par_list, authorship_list):
            self.assertEqual(item.author_alias_id, exp[0].pk)
            self.assertEqual(item.paper_id, exp[1].pk)
            if item.author_alias_id in [alias3.pk, alias4.pk]:
                self.assertIs(item.confirmed, None)
            else:
                self.assertIs(item.confirmed, exp[2])
        event_set.discard((person1, paper2))
        query = (models.FeedEvent.query_model.event_type == event_type)
        qs = models.FeedEvent.objects.filter(query)
        qs = qs.select_related('person', 'paper')
        self.assertEqual(len(qs), len(event_set))
        test_set = set(((x.person, x.paper) for x in qs))
        self.assertEqual(test_set, event_set)

    def test_authorship_acceptance(self):
        # Prepare test data
        partab = models.PaperAuthorReference.query_model
        evtab = models.FeedEvent.query_model
        parobj = models.PaperAuthorReference.objects
        sciswarm_scheme = const.person_alias_schemes.SCISWARM
        email_scheme = const.person_alias_schemes.EMAIL
        event_type = const.user_feed_events.AUTHORSHIP_CONFIRMED
        person_defaults = dict(title_before='', title_after='', bio='')
        user_defaults = dict(password='*', language='en', timezone='UTC',
            is_active=True, is_superuser=False)

        person1 = models.Person.objects.create(username='person1',
            first_name='Test', last_name='User1', **person_defaults)
        user1 = models.User.objects.create(username=person1.username,
            person=person1, **user_defaults)
        alias1 = models.PersonAlias.objects.create(scheme=sciswarm_scheme,
            identifier=person1.base_identifier, target=person1)
        person2 = models.Person.objects.create(username='person2',
            first_name='Test', last_name='User2', **person_defaults)
        user2 = models.User.objects.create(username=person2.username,
            person=person2, **user_defaults)
        alias2 = models.PersonAlias.objects.create(scheme=sciswarm_scheme,
            identifier=person2.base_identifier, target=person2)
        person3 = models.Person.objects.create(username='person3',
            first_name='Test', last_name='User3', **person_defaults)
        user3 = models.User.objects.create(username=person3.username,
            person=person3, **user_defaults)
        alias3 = models.PersonAlias.objects.create(scheme=sciswarm_scheme,
            identifier=person3.base_identifier, target=person3)
        alias4 = models.PersonAlias.objects.create(scheme=email_scheme,
            identifier='foo@example.com', target=person1)

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
        # Deleted review must not affect authorship acceptance
        models.PaperReview.objects.create(posted_by=person2, paper=paper5,
            deleted=True, **review_defaults)
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
                parobj.create(paper=paper, author_alias=alias, confirmed=None)
        models.PaperAlias.objects.create(scheme=sciswarm_scheme,
            identifier='p/' + str(paper6.pk), target=paper6)
        parobj.create(paper=paper2, author_alias=alias4, confirmed=None)

        c = Client(HTTP_HOST='sciswarm.test')

        # Test data: (user, accept/reject, (selected papers),
        # (expected confirmation status after test))
        test_data = [
            (user1, True, tuple(), (None, None, None, None, None)),
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
            confirmed_set = set((k for k,v in exp_map.items() if v))
            query = (partab.author_alias.target == user.person)
            qs = parobj.filter(query)
            tmp = [(x.pk, x.confirmed) for x in qs]
            for item in qs:
                self.assertIs(item.confirmed, exp_map[item.paper_id])
            qs = user.person.feedevent_set.all()
            tmp = set((x.paper_id for x in qs))
            self.assertEqual(tmp, confirmed_set)
            self.assertEqual(qs.count(), len(confirmed_set))
            for item in qs:
                self.assertEqual(item.event_type, event_type)

        test_data = [
            (user1, False, paper3, 1),
            (user1, True, paper3, 1),
            (user1, False, paper1, 1),
            (user1, False, paper2, 2),
            (user1, True, paper2, 2),
            (user2, False, paper1, 1),
            (user2, True, paper2, 1),
            (user2, False, paper2, 1),
            (user3, False, paper1, 1),
            (user3, False, paper3, 1),
        ]

        # Test successful authorship confirmation/rejection
        for user, accept, paper, refcount in test_data:
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
            qs = parobj.filter(query)
            self.assertEqual(len(qs), refcount)
            for item in qs:
                self.assertIs(item.confirmed, accept)
            query = (evtab.paper == paper)
            qs = user.person.feedevent_set.filter(query)
            self.assertEqual(qs.exists(), accept)

        # Test form error checks
        confirmed_query = (partab.confirmed == True)
        rejected_query = (partab.confirmed == False)
        par_count = parobj.count()
        confirmed_count = parobj.filter(confirmed_query).count()
        rejected_count = parobj.filter(rejected_query).count()
        event_count = models.FeedEvent.objects.count()

        url = reverse('core:mass_authorship_confirmation')
        post_data = {fname_tpl % paper4.pk: True}
        c.force_login(user2)
        response = c.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue(form.has_error(NON_FIELD_ERRORS, 'no_action'))
        query = ((partab.author_alias.target == user2.person) &
            (partab.paper == paper4))
        testitem = parobj.get(query)
        self.assertIs(testitem.confirmed, None)
        self.assertEqual(parobj.count(), par_count)
        self.assertEqual(parobj.filter(confirmed_query).count(),
            confirmed_count)
        self.assertEqual(parobj.filter(rejected_query).count(), rejected_count)
        self.assertEqual(models.FeedEvent.objects.count(), event_count)

        kwargs = dict(pk=paper4.pk)
        url = reverse('core:paper_authorship_confirmation', kwargs=kwargs)
        post_data = dict()
        response = c.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue(form.has_error(NON_FIELD_ERRORS, 'no_action'))
        query = ((partab.author_alias.target == user2.person) &
            (partab.paper == paper4))
        testitem = parobj.get(query)
        self.assertIs(testitem.confirmed, None)
        self.assertEqual(parobj.count(), par_count)
        self.assertEqual(parobj.filter(confirmed_query).count(),
            confirmed_count)
        self.assertEqual(parobj.filter(rejected_query).count(), rejected_count)
        self.assertEqual(models.FeedEvent.objects.count(), event_count)

        test_data = [
            (user2, True, paper1),
            (user3, True, paper1),
            (user3, True, paper3),
        ]

        # Test authorship confirmation error (blocked by review)
        for user, accept, paper in test_data:
            query = ((partab.author_alias.target == user.person) &
                (partab.paper == paper))
            testitem = parobj.get(query)
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
            tmp = parobj.get(query)
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
        self.assertEqual(models.FeedEvent.objects.count(), event_count)
