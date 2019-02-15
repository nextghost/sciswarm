#!/usr/bin/python3

from lxml import etree
from core.models import const
from core.utils.harvest import ImportBridge
from .oai import OaiRepository, format_datestamp
import datetime

_nsmap = dict(a='http://arxiv.org/OAI/arXiv/')

_category_defs = {
    'astro-ph': (const.science_fields.ASTRONOMY, 'Astrophysics'),
    'astro-ph.GA': (const.science_fields.ASTRONOMY,'Astrophysics of Galaxies'),
    'astro-ph.CO': (const.science_fields.ASTRONOMY,
        'Cosmology and Nongalactic Astrophysics'),
    'astro-ph.EP': (const.science_fields.ASTRONOMY,
        'Earth and Planetary Astrophysics'),
    'astro-ph.HE': (const.science_fields.ASTRONOMY,
        'High Energy Astrophysical Phenomena'),
    'astro-ph.IM': (const.science_fields.ASTRONOMY,
        'Instrumentation and Methods for Astrophysics'),
    'astro-ph.SR': (const.science_fields.ASTRONOMY,
        'Solar and Stellar Astrophysics'),
    'cond-mat': (const.science_fields.PHYSICS, 'General Condensed Matter'),
    'cond-mat.dis-nn': (const.science_fields.PHYSICS,
        'Disordered Systems and Neural Networks'),
    'cond-mat.mtrl-sci': (const.science_fields.PHYSICS, 'Materials Science'),
    'mtrl-th': (const.science_fields.PHYSICS, 'Materials Science'),
    'cond-mat.mes-hall': (const.science_fields.PHYSICS,
        'Mesoscale and Nanoscale Physics'),
    'cond-mat.other': (const.science_fields.PHYSICS,
        'General Condensed Matter'),
    'cond-mat.quant-gas': (const.science_fields.PHYSICS, 'Quantum Gases'),
    'cond-mat.soft': (const.science_fields.PHYSICS, 'Soft Condensed Matter'),
    'cond-mat.stat-mech': (const.science_fields.PHYSICS,
        'Statistical Mechanics'),
    'cond-mat.str-el': (const.science_fields.PHYSICS,
        'Strongly Correlated Electrons'),
    'cond-mat.supr-con': (const.science_fields.PHYSICS, 'Superconductivity'),
    'supr-con': (const.science_fields.PHYSICS, 'Superconductivity'),
    'gr-qc': (const.science_fields.PHYSICS,
        'General Relativity and Quantum Cosmology'),
    'hep-ex': (const.science_fields.PHYSICS, 'High Energy Physics'),
    'hep-lat': (const.science_fields.PHYSICS, 'High Energy Physics'),
    'hep-ph': (const.science_fields.PHYSICS, 'High Energy Physics'),
    'hep-th': (const.science_fields.PHYSICS, 'High Energy Physics'),
    'math-ph': (const.science_fields.PHYSICS, 'Mathematical Physics'),
    'nlin': (const.science_fields.PHYSICS, 'Nonlinear Sciences'),
    'nlin.AO': (const.science_fields.PHYSICS,
        'Adaptation and Self-Organizing Systems'),
    'adap-org': (const.science_fields.PHYSICS,
        'Adaptation and Self-Organizing Systems'),
    'nlin.CG': (const.science_fields.PHYSICS,
        'Cellular Automata and Lattice Gases'),
    'comp-gas': (const.science_fields.PHYSICS,
        'Cellular Automata and Lattice Gases'),
    'nlin.CD': (const.science_fields.PHYSICS, 'Chaotic Dynamics'),
    'chao-dyn': (const.science_fields.PHYSICS, 'Chaotic Dynamics'),
    'nlin.SI': (const.science_fields.PHYSICS,
        'Exactly Solvable and Integrable Systems'),
    'solv-int': (const.science_fields.PHYSICS,
        'Exactly Solvable and Integrable Systems'),
    'nlin.PS': (const.science_fields.PHYSICS,'Pattern Formation and Solitons'),
    'patt-sol':
        (const.science_fields.PHYSICS, 'Pattern Formation and Solitons'),
    'nucl-ex': (const.science_fields.PHYSICS, 'Nuclear Experiment'),
    'nucl-th': (const.science_fields.PHYSICS, 'Nuclear Theory'),
    'physics': (const.science_fields.PHYSICS, 'General Physics'),
    'physics.acc-ph': (const.science_fields.PHYSICS, 'Accelerator Physics'),
    'acc-phys': (const.science_fields.PHYSICS, 'Accelerator Physics'),
    'physics.app-ph': (const.science_fields.PHYSICS, 'Applied Physics'),
    'physics.ao-ph': (const.science_fields.PHYSICS,
        'Atmospheric and Oceanic Physics'),
    'ao-sci': (const.science_fields.PHYSICS,'Atmospheric and Oceanic Physics'),
    'physics.atom-ph': (const.science_fields.PHYSICS, 'Atomic Physics'),
    'atom-ph': (const.science_fields.PHYSICS, 'Atomic Physics'),
    'physics.atm-clus': (const.science_fields.PHYSICS,
        'Atomic and Molecular Clusters'),
    'physics.bio-ph': (const.science_fields.PHYSICS, 'Biological Physics'),
    'physics.chem-ph': (const.science_fields.PHYSICS, 'Chemical Physics'),
    'chem-ph': (const.science_fields.PHYSICS, 'Chemical Physics'),
    'physics.class-ph': (const.science_fields.PHYSICS, 'Classical Physics'),
    'physics.comp-ph': (const.science_fields.PHYSICS, 'Computational Physics'),
    'physics.data-an': (const.science_fields.PHYSICS,
        'Data Analysis, Statistics and Probability'),
    'bayes-an': (const.science_fields.PHYSICS,
        'Data Analysis, Statistics and Probability'),
    'physics.flu-dyn': (const.science_fields.PHYSICS, 'Fluid Dynamics'),
    'physics.gen-ph': (const.science_fields.PHYSICS, 'General Physics'),
    'physics.geo-ph': (const.science_fields.PHYSICS, 'Geophysics'),
    'physics.hist-ph': (const.science_fields.PHYSICS,
        'History and Philosophy of Physics'),
    'physics.ins-det': (const.science_fields.PHYSICS,
        'Instrumentation and Detectors'),
    'physics.med-ph': (const.science_fields.PHYSICS, 'Medical Physics'),
    'physics.optics': (const.science_fields.PHYSICS, 'Optics'),
    'physics.ed-ph': (const.science_fields.PHYSICS, 'Physics Education'),
    'physics.soc-ph': (const.science_fields.PHYSICS, 'Physics and Society'),
    'physics.plasm-ph': (const.science_fields.PHYSICS, 'Plasma Physics'),
    'plasm-ph': (const.science_fields.PHYSICS, 'Plasma Physics'),
    'physics.pop-ph': (const.science_fields.PHYSICS, 'Popular Physics'),
    'physics.space-ph': (const.science_fields.PHYSICS, 'Space Physics'),
    'quant-ph': (const.science_fields.PHYSICS, 'Quantum Physics'),
    'math': (const.science_fields.MATH, 'General Mathematics'),
    'math.AG': (const.science_fields.MATH, 'Algebraic Geometry'),
    'alg-geom': (const.science_fields.MATH, 'Algebraic Geometry'),
    'math.AT': (const.science_fields.MATH, 'Algebraic Topology'),
    'math.AP': (const.science_fields.MATH, 'Analysis of PDEs'),
    'math.CT': (const.science_fields.MATH, 'Category Theory'),
    'math.CA': (const.science_fields.MATH, 'Classical Analysis and ODEs'),
    'math.CO': (const.science_fields.MATH, 'Combinatorics'),
    'math.AC': (const.science_fields.MATH, 'Commutative Algebra'),
    'math.CV': (const.science_fields.MATH, 'Complex Variables'),
    'math.DG': (const.science_fields.MATH, 'Differential Geometry'),
    'dg-ga': (const.science_fields.MATH, 'Differential Geometry'),
    'math.DS': (const.science_fields.MATH, 'Dynamical Systems'),
    'math.FA': (const.science_fields.MATH, 'Functional Analysis'),
    'funct-an': (const.science_fields.MATH, 'Functional Analysis'),
    'math.GM': (const.science_fields.MATH, 'General Mathematics'),
    'math.GN': (const.science_fields.MATH, 'General Topology'),
    'math.GT': (const.science_fields.MATH, 'Geometric Topology'),
    'math.GR': (const.science_fields.MATH, 'Group Theory'),
    'math.HO': (const.science_fields.MATH, 'History and Overview'),
    'math.IT': (const.science_fields.COMPSCI, 'Information Theory'),
    'math.KT': (const.science_fields.MATH, 'K-Theory and Homology'),
    'math.LO': (const.science_fields.MATH, 'Logic'),
    'math.MP': (const.science_fields.PHYSICS, 'Mathematical Physics'),
    'math.MG': (const.science_fields.MATH, 'Metric Geometry'),
    'math.NT': (const.science_fields.MATH, 'Number Theory'),
    'math.NA': (const.science_fields.MATH, 'Numerical Analysis'),
    'math.OA': (const.science_fields.MATH, 'Operator Algebras'),
    'math.OC': (const.science_fields.MATH, 'Optimization and Control'),
    'math.PR': (const.science_fields.MATH, 'Probability'),
    'math.QA': (const.science_fields.MATH, 'Quantum Algebra'),
    'q-alg': (const.science_fields.MATH, 'Quantum Algebra'),
    'math.RT': (const.science_fields.MATH, 'Representation Theory'),
    'math.RA': (const.science_fields.MATH, 'Rings and Algebras'),
    'math.SP': (const.science_fields.MATH, 'Spectral Theory'),
    'math.ST': (const.science_fields.MATH, 'Statistics Theory'),
    'math.SG': (const.science_fields.MATH, 'Symplectic Geometry'),
    'corr': (const.science_fields.COMPSCI, 'General Computer Science'),
    'cs.AI': (const.science_fields.COMPSCI, 'Artificial Intelligence'),
    'cs.CL': (const.science_fields.COMPSCI, 'Computation and Language'),
    'cmp-lg': (const.science_fields.COMPSCI, 'Computation and Language'),
    'cs.CC': (const.science_fields.COMPSCI, 'Computational Complexity'),
    'cs.CE': (const.science_fields.COMPSCI,
        'Computational Engineering, Finance, and Science'),
    'cs.CG': (const.science_fields.COMPSCI, 'Computational Geometry'),
    'cs.GT': (const.science_fields.COMPSCI, 'Computer Science and Game Theory'),
    'cs.CV': (const.science_fields.COMPSCI,
        'Computer Vision and Pattern Recognition'),
    'cs.CY': (const.science_fields.COMPSCI, 'Computers and Society'),
    'cs.CR': (const.science_fields.COMPSCI, 'Cryptography and Security'),
    'cs.DS': (const.science_fields.COMPSCI, 'Data Structures and Algorithms'),
    'cs.DB': (const.science_fields.COMPSCI, 'Databases'),
    'cs.DL': (const.science_fields.COMPSCI, 'Digital Libraries'),
    'cs.DM': (const.science_fields.COMPSCI, 'Discrete Mathematics'),
    'cs.DC': (const.science_fields.COMPSCI,
        'Distributed, Parallel, and Cluster Computing'),
    'cs.ET': (const.science_fields.COMPSCI, 'Emerging Technologies'),
    'cs.FL': (const.science_fields.COMPSCI,
        'Formal Languages and Automata Theory'),
    'cs.GL': (const.science_fields.COMPSCI, 'General Literature'),
    'cs.GR': (const.science_fields.COMPSCI, 'Graphics'),
    'cs.AR': (const.science_fields.COMPSCI, 'Hardware Architecture'),
    'cs.HC': (const.science_fields.COMPSCI, 'Human-Computer Interaction'),
    'cs.IR': (const.science_fields.COMPSCI, 'Information Retrieval'),
    'cs.IT': (const.science_fields.COMPSCI, 'Information Theory'),
    'cs.LO': (const.science_fields.COMPSCI, 'Logic in Computer Science'),
    'cs.LG': (const.science_fields.COMPSCI, 'Machine Learning'),
    'cs.MS': (const.science_fields.COMPSCI, 'Mathematical Software'),
    'cs.MA': (const.science_fields.COMPSCI, 'Multiagent Systems'),
    'cs.MM': (const.science_fields.COMPSCI, 'Multimedia'),
    'cs.NI': (const.science_fields.COMPSCI,
        'Networking and Internet Architecture'),
    'cs.NE': (const.science_fields.COMPSCI,
        'Neural and Evolutionary Computing'),
    'cs.NA': (const.science_fields.MATH, 'Numerical Analysis'),
    'cs.OS': (const.science_fields.COMPSCI, 'Operating Systems'),
    'cs.OH': (const.science_fields.COMPSCI, 'General Computer Science'),
    'cs.PF': (const.science_fields.COMPSCI, 'Performance'),
    'cs.PL': (const.science_fields.COMPSCI, 'Programming Languages'),
    'cs.RO': (const.science_fields.COMPSCI, 'Robotics'),
    'cs.SI': (const.science_fields.COMPSCI, 'Social and Information Networks'),
    'cs.SE': (const.science_fields.COMPSCI, 'Software Engineering'),
    'cs.SD': (const.science_fields.COMPSCI, 'Sound'),
    'cs.SC': (const.science_fields.COMPSCI, 'Symbolic Computation'),
    'cs.SY': (const.science_fields.COMPSCI, 'Systems and Control'),
    'q-bio': (const.science_fields.BIOLOGY, 'General Quantitative Biology'),
    'q-bio.BM': (const.science_fields.BIOLOGY, 'Biomolecules'),
    'q-bio.CB': (const.science_fields.BIOLOGY, 'Cell Behavior'),
    'q-bio.GN': (const.science_fields.BIOLOGY, 'Genomics'),
    'q-bio.MN': (const.science_fields.BIOLOGY, 'Molecular Networks'),
    'q-bio.NC': (const.science_fields.BIOLOGY, 'Neurons and Cognition'),
    'q-bio.OT': (const.science_fields.BIOLOGY, 'General Quantitative Biology'),
    'q-bio.PE': (const.science_fields.BIOLOGY, 'Populations and Evolution'),
    'q-bio.QM': (const.science_fields.BIOLOGY, 'Quantitative Methods'),
    'q-bio.SC': (const.science_fields.BIOLOGY, 'Subcellular Processes'),
    'q-bio.TO': (const.science_fields.BIOLOGY, 'Tissues and Organs'),
    'q-fin': (const.science_fields.SOCIAL, 'Quantitative Finance'),
    'q-fin.CP': (const.science_fields.SOCIAL, 'Computational Finance'),
    'q-fin.EC': (const.science_fields.SOCIAL, 'Economics'),
    'q-fin.GN': (const.science_fields.SOCIAL, 'General Finance'),
    'q-fin.MF': (const.science_fields.SOCIAL, 'Mathematical Finance'),
    'q-fin.PM': (const.science_fields.SOCIAL, 'Portfolio Management'),
    'q-fin.PR': (const.science_fields.SOCIAL, 'Pricing of Securities'),
    'q-fin.RM': (const.science_fields.SOCIAL, 'Risk Management'),
    'q-fin.ST': (const.science_fields.SOCIAL, 'Statistical Finance'),
    'q-fin.TR': (const.science_fields.SOCIAL,
        'Trading and Market Microstructure'),
    'stat': (const.science_fields.MATH, 'General Statistics'),
    'stat.AP': (const.science_fields.MATH, 'Statistical Applications'),
    'stat.CO': (const.science_fields.MATH, 'Statistical Computation'),
    'stat.ML': (const.science_fields.COMPSCI, 'Machine Learning'),
    'stat.ME': (const.science_fields.MATH, 'Statistical Methodology'),
    'stat.OT': (const.science_fields.MATH, 'General Statistics'),
    'stat.TH': (const.science_fields.MATH, 'Statistics Theory'),
    'eess': (const.science_fields.ENGINEERING,
        'Electrical Engineering and Systems Science'),
    'eess.AS': (const.science_fields.ENGINEERING,
        'Audio and Speech Processing'),
    'eess.IV': (const.science_fields.ENGINEERING,'Image and Video Processing'),
    'eess.SP': (const.science_fields.ENGINEERING, 'Signal Processing'),
    'econ': (const.science_fields.SOCIAL, 'Economics'),
    'econ.EM': (const.science_fields.SOCIAL, 'Econometrics'),
    'econ.GN': (const.science_fields.SOCIAL, 'General Economics'),
    'econ.TH': (const.science_fields.SOCIAL, 'Theoretical Economics'),
}

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

def parse_arxiv_meta(record):
    ret = dict()
    arxiv_id = _single_node(record, 'a:id').text.strip()
    ret['id'] = arxiv_id
    ret['primary_identifier'] = (const.paper_alias_schemes.ARXIV, arxiv_id)
    ret['identifiers'] = [ret['primary_identifier']]
    ret['name'] = _single_node(record, 'a:title').text.strip()
    ret['abstract'] = _single_node(record, 'a:abstract').text.strip()

    nodeset = record.xpath('a:doi', namespaces=_nsmap)
    for node in nodeset:
        ret['identifiers'].append((const.paper_alias_schemes.DOI,
            node.text.strip()))

    subfields = []
    node = _optional_node(record, 'a:categories')
    if node is not None:
        ret['categories'] = node.text.strip().split()

    author_list = []
    for node in record.xpath('a:authors/a:author', namespaces=_nsmap):
        name = _single_node(node, 'a:keyname').text.strip()
        subnode = _optional_node(node, 'a:forenames')
        if subnode is not None:
            tmp = subnode.text.strip()
            if tmp:
                name += ', ' + tmp
        author_list.append(name)
    ret['author_names'] = author_list
    return ret

def harvest():
    repo = OaiRepository('http://export.arxiv.org/oai2')
    bridge = ImportBridge('arxiv', repo.repositoryName, 'arXiv Bot')
    bridge.map_categories(_category_defs)
    cursor = bridge.import_cursor()
    day = datetime.timedelta(days=1)
    if cursor:
        cursor = repo.parse_datestamp(cursor)
    else:
        cursor = repo.earliestDatestamp
    while cursor <= datetime.date.today():
        data = repo.list_records('arXiv', cursor, cursor)
        paper_list = [parse_arxiv_meta(x.metadata) for x in data
            if x.metadata is not None]
        del data
        bridge.import_papers(format_datestamp(cursor), paper_list)
        cursor += day
