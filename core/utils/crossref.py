from django.forms import ValidationError
from django.http import QueryDict
from django.utils.html import strip_tags
from core.models import const
from core import models
from .validators import (doi_validator, filter_wrapper, validate_paper_alias,
    validate_person_alias)
from html import unescape
from urllib.parse import quote
import re
import requests
import time

def crossref_import_bridge():
    from .harvest import ImportBridge
    return ImportBridge('crossref', 'Crossref', 'Crossref Bot')

def crossref_parse_work(data):
    doi_scheme = const.paper_alias_schemes.DOI
    isbn_scheme = const.paper_alias_schemes.ISBN
    orcid_scheme = const.person_alias_schemes.ORCID
    doi = doi_validator(data['DOI'])
    ret = dict()
    ret['id'] = doi
    ret['name'] = None
    title_list = data.get('title')
    if title_list:
        ret['name'] = title_list[0]
    abstract = data.get('abstract', '(Abstract not available)')
    if re.match(r'<[a-z]', abstract, re.I):
        abstract = unescape(strip_tags(abstract))
    ret['abstract'] = abstract
    ret['primary_identifier'] = (doi_scheme, doi)
    ret['year_published'] = data['issued']['date-parts'][0][0]
    id_list = [(doi_scheme, doi)]

    if data['type'] == 'book':
        for isbn in data.get('ISBN', []):
            try:
                id_list.append(validate_paper_alias(isbn_scheme, isbn))
            except ValidationError:
                pass
    ret['identifiers'] = id_list

    author_list = []
    author_names = []
    bibliography = []
    author_keys = ('family', 'given', 'name')

    for item in data.get('author', []):
        if 'ORCID' in item:
            orcid = item['ORCID'].rsplit('/', 1)[-1]
            try:
                author_list.append(validate_person_alias(orcid_scheme, orcid))
                continue
            except ValidationError:
                pass
        tokens = [item.get(k) for k in author_keys]
        tokens = [x for x in tokens if x]
        author_names.append(', '.join(tokens))

    for item in data.get('reference', []):
        if 'DOI' in item:
            try:
                alias = validate_paper_alias(doi_scheme, item['DOI'])
                bibliography.append(alias)
                continue
            except ValidationError:
                pass
        if 'ISBN' in item:
            isbn = item['ISBN'].rsplit('/', 1)[-1]
            try:
                bibliography.append(validate_paper_alias(isbn_scheme, isbn))
                continue
            except ValidationError:
                pass

    ret['authors'] = author_list
    ret['author_names'] = author_names
    ret['bibliography'] = bibliography
    return ret

def crossref_fetch(doi):
    baseurl = 'https://api.crossref.org/works/'
    url = baseurl + quote(doi, safe='')
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    if data['status'] != 'ok' or data['message-type'] != 'work':
        raise RuntimeError('Bad response')
    return crossref_parse_work(data['message'])

def _crossref_list_url(doi_list):
    from django.http import QueryDict
    baseurl = 'https://api.crossref.org/works?'
    args = QueryDict(mutable=True)
    args['filter'] = ','.join(('doi:' + x for x in doi_list))
    args['rows'] = 1000
    return baseurl + args.urlencode()

def crossref_fetch_list(doi_list, delay=1):
    from .harvest import harvest_logger
    check_alias = filter_wrapper(doi_validator)

    # Basic input validation
    doi_list = [x for x in doi_list if check_alias(x)]
    bad_dois = [x for x in doi_list if ',' in x]
    doi_list = [x for x in doi_list if ',' not in x]
    size_list = [len(quote('doi:%s,' % x)) for x in doi_list]
    batch_size = 128
    max_url_length = 3500
    pos = 0
    ret = []

    # Run batch queries
    while pos < len(doi_list):
        # Find how many DOIs will fit into the URL
        arg_count = 1
        url_length = size_list[pos]
        while arg_count < batch_size and pos + arg_count < len(size_list):
            tmp = size_list[pos + arg_count]
            if url_length + tmp > max_url_length:
                break
            arg_count += 1
            url_length += tmp

        # Run the query
        while True:
            data = None
            batch_list = doi_list[pos:pos+arg_count]
            url = _crossref_list_url(batch_list)
            if delay:
                time.sleep(delay)
            try:
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                if data['status']!='ok' or data['message-type']!='work-list':
                    raise RuntimeError('Bad response')
                break
            except:
                # Bisect the DOI list to find and skip the invalid DOI
                if arg_count > 1:
                    arg_count = arg_count // 2
                    continue
                else:
                    data = None
                    pos += len(batch_list)
                    log_msg = 'Crossref query returned error. DOIs: %(doi)s'
                    kwargs = dict(doi=str(batch_list))
                    harvest_logger.warning(log_msg, kwargs, exc_info=True)
                    break

        # Process the response
        if data is not None:
            total = int(data['message']['total-results'])
            work_list = data['message']['items']
            if total > len(work_list):
                log_msg = "Crossref response didn't fit into one page: %(url)s"
                kwargs = dict(count=batch_count, url=url)
                harvest_logger.warning(log_msg, kwargs)
            ret.extend((crossref_parse_work(x) for x in work_list))
            pos += len(batch_list)

    # DOIs containing comma could result in invalid filter query,
    # fetch them individually
    for doi in bad_dois:
        if delay:
            time.sleep(delay)
        try:
            ret.append(crossref_fetch(doi))
        except:
            log_msg = 'Crossref query returned error. DOIs: %(doi)s'
            kwargs = dict(doi=doi)
            harvest_logger.warning(log_msg, kwargs, exc_info=True)
    return ret
