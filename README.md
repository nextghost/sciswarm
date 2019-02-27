# Sciswarm

A scientific social network focused on papers and altmetrics.

Post metadata about your papers (with external download links), follow updates from your colleagues, review and share their work. The goal of this project is to turn preprint repositories like arXiv into equally prestigious publishing venues as the big journals.

The long-term vision for this project is to create a distributed network of Sciswarm servers operated by research institutions themselves.

## Dependencies

- PostgreSQL 9.6+
- Psycopg2
- Python 3.5+
- Django 1.10+
- pytz
- Babel
- requests, lxml (harvest scripts only)

The current target platform for this project is Debian Stretch. Pull requests must work with the minimum versions listed above.

Sciswarm is licensed under GNU Affero GPL v3. This repository contains a copy of [jQuery](http://jquery.com/), licensed under [MIT license](https://jquery.org/license/).
