from lxml import etree
import requests
import datetime
import math
import re
import time

__all__ = ['OaiError', 'OaiRepository', 'format_datestamp']

_nsmap = dict(oai='http://www.openarchives.org/OAI/2.0/')

def _optional_node(node, xpath):
    ret = node.xpath(xpath, namespaces=_nsmap)

    if len(ret) > 1:
        err = 'XPath query returned too many results: {0}'
        raise RuntimeError(err.format(len(ret)))
    elif len(ret) == 1:
        return ret[0]
    return None

def _single_node(node, xpath):
    ret = node.xpath(xpath, namespaces=_nsmap)
    if len(ret) != 1:
        err = 'XPath query returned unexpected number of results: {0}'
        raise RuntimeError(err.format(len(ret)))
    return ret[0]

def _parse_datetime(datestr):
    return datetime.datetime.strptime(datestr, '%Y-%m-%dT%H:%M:%SZ')

def _parse_date(datestr):
    return datetime.datetime.strptime(datestr, '%Y-%m-%d').date()

def format_datestamp(dateval):
    if isinstance(dateval, datetime.datetime):
        if dateval.tzinfo is not None:
            dateval = dateval.astimezone(datetime.timezone.utc)
        return dateval.strftime('%Y-%m-%dT%H:%M:%SZ')
    elif isinstance(dateval, datetime.date):
        return dateval.isoformat()
    return dateval

def _parse_delay(delay):
    if delay.isdigit():
        return int(delay)

    format_list = [
        (r'^[A-Za-z]+, (?P<pre>\d{2}) (?P<mon>[A-Za-z]+) (?P<post>\d{4} \d{2}:\d{2}:\d{2}) (?:GMT|UTC)', '%(pre)s %(mon)02d %(post)s', '%d %m %Y %H:%M:%S'),
        (r'^[A-Za-z]+, (?P<pre>\d{2})-(?P<mon>[A-Za-z]+)-(?P<post>\d{2} \d{2}:\d{2}:\d{2}) (?:GMT|UTC)', '%(pre)s %(mon)02d %(post)s', '%d %m %y %H:%M:%S'),
        (r'^[A-Za-z]+ (?P<mon>[A-Za-z]+) (?P<post>\d{2} \d{2}:\d{2}:\d{2} \d{4})', '%(mon)02d %(post)s', '%m %d %H:%M:%S %Y'),
    ]
    month_list = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug',
        'Sep', 'Oct', 'Nov', 'Dec']

    for regex, tpl, parse_fmt in format_list:
        match = re.match(regex, delay)
        if match:
            args = match.groupdict()
            args['mon'] = month_list.index(args['mon']) + 1
            datestr = tpl % args
            dateval = datetime.datetime.strptime(datestr, parse_fmt)
            now = datetime.datetime.utcnow()
            return max(0, math.ceil((dateval - now).total_seconds()))
    else:
        raise ValueError('Invalid delay value: %s' % delay)

class OaiError(RuntimeError):
    def __init__(self, message, code):
        super(OaiError, self).__init__(message)
        self.code = code

class OaiMetadataFormat(object):
    def __init__(self, xml_node):
        self.prefix = _single_node(xml_node, 'oai:metadataPrefix').text
        self.schema = _single_node(xml_node, 'oai:schema').text
        self.namespace = _single_node(xml_node, 'oai:metadataNamespace').text

class OaiSet(object):
    def __init__(self, xml_node):
        self.code = _single_node(xml_node, 'oai:setSpec').text
        self.name = _single_node(xml_node, 'oai:setName').text
        nodeset = xml_node.xpath('oai:setDescription/*', namespaces=_nsmap)
        self.description = list(nodeset)

class OaiRecord(object):
    def __init__(self, repo, xml_node):
        # ListIdentifiers returns only list of bare headers
        if xml_node.tag == '{%s}header' % _nsmap['oai']:
            header = xml_node
            self.metadata = None
            self.about = None
        else:
            header = _single_node(xml_node, 'oai:header')
            self.metadata = _optional_node(xml_node, 'oai:metadata/*')
            self.about = list(xml_node.xpath('oai:about/*', namespaces=_nsmap))
        self.id = _single_node(header, 'oai:identifier').text
        node = _single_node(header, 'oai:datestamp')
        self.datestamp = repo.parse_datestamp(node.text)
        nodeset = header.xpath('oai:setSpec', namespaces=_nsmap)
        self.setSpec = [x.text for x in nodeset]
        self.deleted = (header.attrib.get('status') == 'deleted')

class OaiRepository(object):
    def __init__(self, url):
        self._url = url
        xml = self._query('Identify')
        node = _single_node(xml, '/oai:OAI-PMH/oai:Identify')
        element_list = ['repositoryName', 'baseURL', 'protocolVersion',
            'deletedRecord', 'granularity']
        for item in element_list:
            setattr(self, item, _single_node(node, 'oai:' + item).text)
        if self.protocolVersion != '2.0':
            msg = 'Unsupported OAI protocol versions %s.'
            raise RuntimeError(msg % self.protocolVersion)

        if self.granularity == 'YYYY-MM-DD':
            self.parse_datestamp = _parse_date
        elif self.granularity == 'YYYY-MM-DDThh:mm:ssZ':
            self.parse_datestamp = _parse_datetime
        else:
            raise RuntimeError('Repository uses unsupported datestamp format.')
        tmp = _single_node(node, 'oai:earliestDatestamp').text
        self.earliestDatestamp = self.parse_datestamp(tmp)

        self.adminEmails = []
        for tmp in node.xpath('oai:adminEmail', namespaces=_nsmap):
            self.adminEmails.append(tmp.text)
        self.compression = []
        for tmp in node.xpath('oai:compression', namespaces=_nsmap):
            self.compression.append(tmp.text)
        nodelist = node.xpath('oai:description/*', namespaces=_nsmap)
        self.description = list(nodelist)

    def _query(self, verb, args=dict()):
        params = args.copy()
        params['verb'] = verb
        while True:
            res = requests.get(self._url, params=params)
            if res.status_code == 503 and 'retry-after' in res.headers:
                secs = _parse_delay(res.headers['retry-after'])
                time.sleep(secs)
                continue
            res.raise_for_status()
            xml = etree.fromstring(res.content)
            node = _optional_node(xml, '/oai:OAI-PMH/oai:error')
            if node is not None:
                raise OaiError(node.text, node.attrib['code'])
            return xml

    def list_metadata_formats(self, identifier=None):
        args = dict()
        if identifier is not None:
            args['identifier'] = identifier
        try:
            xml = self._query('ListMetadataFormats', args)
        except OaiError as e:
            if e.code == 'noMetadataFormats':
                return []
            raise
        query = '/oai:OAI-PMH/oai:ListMetadataFormats/oai:metadataFormat'
        nodeset = xml.xpath(query, namespaces=_nsmap)
        return [OaiMetadataFormat(x) for x in nodeset]

    def list_sets(self):
        args = dict()
        data = []
        while True:
            try:
                xml = self._query('ListSets', args)
            except OaiError as e:
                if e.code == 'noSetHierarchy':
                    return data
                raise
            node = _single_node(xml, '/oai:OAI-PMH/oai:ListSets')
            nodeset = node.xpath('oai:set', namespaces=_nsmap)
            data.extend((OaiSet(x) for x in nodeset))
            token = _optional_node(node, 'oai:resumptionToken')
            if token is None or not token.text:
                return data
            args = dict(resumptionToken=token.text)

    def get_record(self, identifier, metadataPrefix):
        args = dict(identifier=identifier, metadataPrefix=metadataPrefix)
        xml = self._query('GetRecord', args)
        node = _single_node(xml, '/oai:OAI-PMH/oai:GetRecord/oai:record')
        return OaiRecord(self, node)

    def list_identifiers(self, prefix, start=None, end=None, setcode=None):
        args = dict(metadataPrefix=prefix)
        if start is not None:
            args['from'] = format_datestamp(start)
        if end is not None:
            args['until'] = format_datestamp(end)
        if setcode is not None:
            args['set'] = setcode
        data = []
        while True:
            try:
                xml = self._query('ListIdentifiers', args)
            except OaiError as e:
                if e.code == 'noRecordsMatch':
                    return data
                raise
            node = _single_node(xml, '/oai:OAI-PMH/oai:ListIdentifiers')
            nodeset = node.xpath('oai:header', namespaces=_nsmap)
            data.extend((OaiRecord(self, x) for x in nodeset))
            token = _optional_node(node, 'oai:resumptionToken')
            if token is None or not token.text:
                return data
            args = dict(resumptionToken=token.text)

    def list_records(self, prefix, start=None, end=None, setcode=None):
        args = dict(metadataPrefix=prefix)
        if start is not None:
            args['from'] = format_datestamp(start)
        if end is not None:
            args['until'] = format_datestamp(end)
        if setcode is not None:
            args['set'] = setcode
        data = []
        while True:
            try:
                xml = self._query('ListRecords', args)
            except OaiError as e:
                if e.code == 'noRecordsMatch':
                    return data
                raise
            node = _single_node(xml, '/oai:OAI-PMH/oai:ListRecords')
            nodeset = node.xpath('oai:record', namespaces=_nsmap)
            data.extend((OaiRecord(self, x) for x in nodeset))
            token = _optional_node(node, 'oai:resumptionToken')
            if token is None or not token.text:
                return data
            args = dict(resumptionToken=token.text)
