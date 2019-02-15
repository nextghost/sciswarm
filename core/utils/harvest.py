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

from collections import OrderedDict
from django.conf import settings
from django.db import IntegrityError
from django.db.transaction import atomic
from . import pgsql
from .transaction import lock_record
from .utils import fold_or, list_map
from ..models import const
from .. import models
import logging
import re

harvest_logger = logging.getLogger('sciswarm.harvest')

def clean_paper_list(paper_list):
    alias_map = dict()
    log_msg = 'Duplicate alias [%(scm)s, %(id)s] referenced by papers "%(pa)s", "%(pb)s".'
    id_map = OrderedDict(((x['id'], x) for x in paper_list))
    paper_list = list(id_map.values())
    for paper in paper_list:
        abstract = paper['abstract']
        abstract = re.sub(r'([^\n])\n([^\n])', r'\1 \2', abstract, flags=re.M)
        paper['abstract'] = abstract

        clean_identifiers = []
        for alias in paper.get('identifiers', []):
            other = alias_map.get(alias)
            # Remove alias from the old paper, leave it on the new paper
            if other is None:
                alias_map[alias] = paper
            elif other['id'] != paper['id']:
                kwargs = dict(scm=const.paper_alias_schemes[alias[0]],
                    id=alias[1], pa=other['id'], pb=paper['id'])
                harvest_logger.warning(log_msg, kwargs)
                continue
            clean_identifiers.append(alias)
        paper['identifiers'] = clean_identifiers
    return paper_list

class ImportBridge(object):
    def __init__(self, code, reponame, botname):
        srcobj = models.PaperImportSource.objects
        query = (models.PaperImportSource.query_model.code == code)
        with atomic():
            pgsql.lock_table(models.Person, pgsql.LOCK_SHARE_ROW_EXCLUSIVE)
            obj = srcobj.filter(query).select_related('bot_profile').first()
            if obj is None:
                username = code + '-bot'
                bio = 'Robot account in charge of automatically importing new papers from %s.'
                scheme = const.person_alias_schemes.SCISWARM
                try:
                    person = models.Person.objects.create(username=username,
                        title_before='', first_name='', last_name=botname,
                        title_after='', bio=bio % reponame)
                    models.User.objects.create(person=person, password='*',
                        username=username, language=settings.LANGUAGE_CODE,
                        first_name='', last_name=botname, email='',
                        is_active=True, is_superuser=False)
                    models.PersonAlias.objects.link_alias(scheme,
                        person.base_identifier, person)
                    obj = srcobj.create(code=code, name=reponame,
                        bot_profile=person, import_cursor='')
                except IntegrityError as e:
                    msg = 'Cannot create bot profile or import source record for %s.'
                    raise RuntimeError(msg % reponame) from e
        self.record = obj
        self.category_map = dict()

    def import_cursor(self):
        return self.record.import_cursor

    def map_categories(self, subfield_defs):
        name_set = set((s for f,s in subfield_defs.values()))
        fobj = models.ScienceSubfield.objects
        with atomic():
            pgsql.lock_table(models.ScienceSubfield,
                pgsql.LOCK_SHARE_ROW_EXCLUSIVE)
            obj_map = dict(((x.name, x) for x in fobj.all()))
            # Ignore obj.field, only the obj.name matters for existing records
            diff_set = name_set - set(obj_map)
            if diff_set:
                # Remove duplicate values
                value_set = set(subfield_defs.values())
                create_list = [models.ScienceSubfield(field=f, name=n)
                    for f,n in value_set if n in diff_set]
                obj_list = fobj.bulk_create(create_list)
                # bulk_create() can assign primary keys only on PostgreSQL
                obj_map.update(((x.name, x) for x in obj_list))
        catmap = dict(((k, obj_map[n]) for k,(f,n) in subfield_defs.items()))
        self.category_map = catmap

    def import_papers(self, cursor, paper_list):
        if not paper_list:
            return
        paper_list = clean_paper_list(paper_list)

        # Convert remote categories to local scientific subfields
        log_msg = 'Unknown category %(cat)s for %(src)s paper %(paper)s'
        for item in paper_list:
            cat_list = item.get('categories', [])
            subfields = item.get('subfields', [])
            for cat in cat_list:
                if cat in self.category_map:
                    subfields.append(self.category_map[cat])
                else:
                    kwargs = dict(cat=cat, src=self.record.name,
                        paper=item['id'])
                    harvest_logger.warning(log_msg, kwargs)
            item['subfields'] = subfields

        # Save new papers into database
        batch_size = 100
        batch_count = (len(paper_list) + batch_size - 1) // batch_size
        with atomic():
            tmp = lock_record(self.record)
            if tmp is None:
                raise RuntimeError('Cannot lock import status record.')
            elif tmp.import_cursor != self.record.import_cursor:
                msg = 'Concurrent %s import process detected.'
                raise RuntimeError(msg % self.record.name)
            pgsql.lock_table(models.PaperAlias, pgsql.LOCK_SHARE_ROW_EXCLUSIVE)
            for batch in range(batch_count):
                pos = batch * batch_size
                self._import_batch(paper_list[pos:pos+batch_size])
            self.record.import_cursor = cursor
            self.record.save(update_fields=['import_cursor'])

    def _import_batch(self, paper_list):
        # Look for existing papers in this batch
        aliastab = models.PaperAlias.query_model
        alias_list = [a for p in paper_list for a in p.get('identifiers', [])]
        alias_groups = list_map(alias_list)
        cond_list = [((aliastab.scheme == s) & aliastab.identifier.belongs(i))
            for s,i in alias_groups.items()]
        query = (aliastab.target.notnull() & fold_or(cond_list))
        qs = models.PaperAlias.objects.filter(query).select_related('target')
        alias_map = dict((((x.scheme, x.identifier), x.target) for x in qs))

        # Load other identifiers of existing papers
        old_paper_map = dict(((x.pk, {}) for x in alias_map.values()))
        if alias_map:
            query = (aliastab.target.pk.belongs(list(old_paper_map)))
            qs = models.PaperAlias.objects.filter(query)
            for item in qs:
                tmp = old_paper_map[item.target_id].setdefault(item.scheme, [])
                tmp.append(item.identifier)

        for paper in paper_list:
            primary_alias = paper.get('primary_identifier')
            new_alias_set = set()
            paper_set = set()
            for alias in paper.get('identifiers', []):
                if alias in alias_map:
                    paper_set.add(alias_map[alias])
                else:
                    new_alias_set.add(alias)

            obj = None
            if primary_alias is not None:
                obj = alias_map.get(primary_alias)
            if obj is None:
                # Alias conflict
                if len(paper_set) > 1:
                    log_msg = 'Aliases of %(src)s paper %(paper)s reference multiple existing papers. Update skipped.'
                    kwargs = dict(src=self.record.name, paper=paper['id'])
                    harvest_logger.warning(log_msg, kwargs)
                    continue
                # Single existing paper, just add missing aliases
                # Don't update the changed_by field because it'd require
                # too aggressive table locking to prevent deadlock
                # If the existing paper already has a different primary alias
                # (same scheme, different identifier), it's a different paper.
                elif paper_set:
                    obj = paper_set.pop()
                    tmp_map = old_paper_map.get(obj.pk, dict())
                    if (primary_alias is not None and
                        tmp_map.get(primary_alias[0])):
                        obj = None
                        log_msg = 'Some aliases of %(src)s paper %(paper)s are assigned to existing papers. Importing paper with partial alias list.'
                        kwargs = dict(src=self.record.name, paper=paper['id'])
                        harvest_logger.warning(log_msg, kwargs)
            elif paper_set and paper_set != set([obj]):
                log_msg = 'Some aliases of %(src)s paper %(paper)s are assigned to other existing papers. Updating paper with partial alias list.'
                kwargs = dict(src=self.record.name, paper=paper['id'])
                harvest_logger.warning(log_msg, kwargs)

            # Update
            if obj is not None:
                for alias in new_alias_set:
                    models.PaperAlias.objects.link_alias(alias[0],alias[1],obj)
            # Paper not found, create it
            else:
                tmp = paper.copy()
                tmp['identifiers'] = new_alias_set
                self._create_paper(tmp)

    def _create_paper(self, paper):
        aaobj = models.PersonAlias.objects
        paobj = models.PaperAlias.objects
        bot_profile = self.record.bot_profile
        defaults = dict(contents_theory=False, contents_survey=False,
            contents_observation=False, contents_experiment=False,
            contents_metaanalysis=False, year_published=None,
            cite_as='')
        kwargs = dict((k, paper.get(k, d)) for k,d in defaults.items())
        obj = models.Paper.objects.create(name=paper['name'],
            abstract=paper['abstract'], posted_by=bot_profile,
            changed_by=bot_profile, incomplete_metadata=True, **kwargs)
        obj.fields.add(*paper['subfields'])

        # Create aliases
        for alias in paper.get('identifiers', []):
            paobj.link_alias(alias[0], alias[1], obj)

        # Create authors
        author_set = set(paper.get('authors', []))
        author_aliases = [aaobj.create_alias(x[0], x[1]) for x in author_set]
        par_list = [models.PaperAuthorReference(paper=obj, author_alias=x,
            confirmed=None) for x in author_aliases]
        if par_list:
            models.PaperAuthorReference.bulk_create(par_list)

        # Create author names
        mfield = models.PaperAuthorName._meta.get_field('author_name')
        max_len = mfield.max_length
        pan_list = [models.PaperAuthorName(paper=obj, author_name=x[:max_len])
            for x in paper.get('author_names', [])]
        if pan_list:
            models.PaperAuthorName.objects.bulk_create(pan_list)

        # Create bibliography
        cite_set = set(paper.get('bibliography', []))
        cite_list = [paobj.create_alias(x[0], x[1]) for x in cite_set]
        if cite_list:
            paper.bibliography.add(*cite_list)

        # Create keywords
        max_len = models.PaperKeyword._meta.get_field('keyword').max_length
        keyword_list = [models.PaperKeyword(paper=obj, keyword=x[:max_len])
            for x in paper.get('keywords', [])]
        if keyword_list:
            models.PaperKeyword.objects.bulk_create(keyword_list)

        models.FeedEvent.objects.create(person=bot_profile, paper=obj,
            event_type=const.user_feed_events.PAPER_POSTED)
        return obj
