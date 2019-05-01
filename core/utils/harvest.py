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
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError
from django.db.models import Count
from django.db.transaction import atomic
from . import pgsql
from .transaction import lock_record
from .utils import fold_or, list_map, make_chunks
from ..models import const
from .. import models
import difflib
import logging
import re

harvest_logger = logging.getLogger('sciswarm.harvest')

def normalize_title(title):
    return ' '.join(title.casefold().split())

def _add_bibliography_batch(data_list):
    id_map = dict()
    for item in data_list:
        scheme, identifier = item['primary_identifier']
        id_map.setdefault(scheme, []).append(identifier)

    # Load papers for sanity checks
    max_id_length = models.PaperAlias._meta.get_field('identifier').max_length
    aliastab = models.PaperAlias.query_model
    cond_list = [((aliastab.scheme == s) & aliastab.identifier.belongs(ids))
        for s,ids in id_map.items()]
    query = fold_or(cond_list) & aliastab.target.pk.notnull()
    pgsql.lock_table(models.PaperAlias, pgsql.LOCK_SHARE_ROW_EXCLUSIVE)
    qs = models.PaperAlias.objects.filter(query).select_related('target')
    qs = qs.defer('target__abstract', 'target__cite_as')
    qs = qs.annotate(bib_count=Count(aliastab.target.bibliography.f()))
    paper_map = dict((((x.scheme, x.identifier), x) for x in qs))
    merge_list = []
    create_set = set()

    for item in data_list:
        pid = tuple(item['primary_identifier'])
        alias = paper_map.get(pid)
        if alias is None:
            log_msg = 'add_bibliography(): Paper not found. Alias: %(pid)s'
            kwargs = dict(pid=pid)
            harvest_logger.warning(log_msg, kwargs)
            continue
        tmp_list = [(s,i) for s,i in item['bibliography']
            if len(i) <= max_id_length]
        item['bibliography'] = tmp_list

        # We're importing bibliography from a different source here.
        # Compare titles to check that the primary alias is assigned correctly.
        paper = alias.target
        if item['name'] is not None:
            check = difflib.SequenceMatcher(None, normalize_title(paper.name),
                normalize_title(item['name']))
            ratio = check.ratio()
            if ratio < 0.5:
                log_msg = 'add_bibliography(): Paper name mismatch (similarity: %(ratio)4.2f). Alias: %(pid)s'
                kwargs = dict(pid=pid, ratio=ratio)
                harvest_logger.warning(log_msg, kwargs)
                continue
        # Paper already has bibliography or there's nothing to add => skip
        if alias.bib_count > 0 or not item['bibliography']:
            continue
        merge_list.append((paper, item))
        create_set.update((tuple(x) for x in item['bibliography']))

    # Create all cited aliases in one big batch
    create_list = [models.PaperAlias(scheme=s, identifier=i)
        for s,i in create_set]
    if not create_list:
        return
    alias_list = models.PaperAlias.objects.bulk_create(create_list)
    alias_map = dict((((x.scheme, x.identifier), x) for x in alias_list))

    # Add aliases to individual papers
    for paper, data in merge_list:
        # Remove duplicates using temporary set
        bib_set = set((tuple(x) for x in data['bibliography']))
        bib_list = [alias_map[x] for x in bib_set]
        paper.bibliography.add(*bib_list)

# Call add_bibliography() with a list of dicts in the same format that
# would be passed to ImportBridge.import_papers()
def add_bibliography(data_list):
    batch_size = 100
    for batch_list in make_chunks(data_list, batch_size):
        with atomic():
            _add_bibliography_batch(batch_list)

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
                    models.User.objects.create(person=person,
                        password=make_password(None), username=username,
                        language=settings.LANGUAGE_CODE, first_name='',
                        last_name=botname, email='', is_active=True,
                        is_superuser=False)
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

    def import_papers(self, cursor, paper_list, query_crossref=False):
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
        new_aliases = []
        with atomic():
            tmp = lock_record(self.record)
            if tmp is None:
                raise RuntimeError('Cannot lock import status record.')
            elif tmp.import_cursor != self.record.import_cursor:
                msg = 'Concurrent %s import process detected.'
                raise RuntimeError(msg % self.record.name)
            pgsql.lock_table(models.PaperAlias, pgsql.LOCK_SHARE_ROW_EXCLUSIVE)
            for batch_list in make_chunks(paper_list, batch_size):
                tmp_papers, tmp_aliases = self._import_batch(batch_list)
                new_aliases.extend(tmp_aliases)
            self.record.import_cursor = cursor
            self.record.save(update_fields=['import_cursor'])
        if query_crossref:
            from .crossref import crossref_fetch_list
            doi_scheme = const.paper_alias_schemes.DOI
            doi_list = [i for s,i in new_aliases if s == doi_scheme]
            for batch in make_chunks(doi_list, 1000):
                cr_data = crossref_fetch_list(batch)
                add_bibliography(cr_data)

    def _import_batch(self, paper_list):
        id_field = models.PaperAlias._meta.get_field('identifier')
        max_id_length = id_field.max_length
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

        created_papers = []
        linked_aliases = []
        for paper in paper_list:
            primary_alias = paper.get('primary_identifier')
            new_alias_set = set()
            paper_set = set()
            for alias in paper.get('identifiers', []):
                if alias in alias_map:
                    paper_set.add(alias_map[alias])
                elif len(alias[1]) <= max_id_length:
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
                linked_aliases.extend(new_alias_set)
            # Paper not found, create it
            else:
                tmp = paper.copy()
                tmp['identifiers'] = new_alias_set
                created_papers.append(self._create_paper(tmp))
                linked_aliases.extend(new_alias_set)
        return (created_papers, linked_aliases)

    def _create_paper(self, paper):
        id_field = models.PaperAlias._meta.get_field('identifier')
        max_id_length = id_field.max_length
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
        paobj.link_alias(const.paper_alias_schemes.SCISWARM,
            obj.base_identifier, obj)
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
        create_list = [models.PaperAlias(scheme=s, identifier=i)
            for s,i in cite_set if len(i) <= max_id_length]
        if create_list:
            cite_list = paobj.bulk_create(create_list)
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
