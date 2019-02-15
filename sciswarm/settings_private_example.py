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

# Installation-specific settings.

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = ''

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

import os

ALLOWED_HOSTS = []

# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': '',
        'USER': '',
        'PASSWORD': ''
    }
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(asctime)s %(levelname)s %(message)s'
        }
    },
    'handlers': {
        'sciswarm_file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': '/var/log/django/sciswarm.log',
            'formatter': 'simple',
        },
        'stderr': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'sciswarm': {
            'handlers': ['sciswarm_file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'sciswarm.harvest': {
            'handlers': ['stderr'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

SECURE_HSTS_INCLUDE_SUBDOMAINS = True

#EMAIL_HOST = 'localhost'
#EMAIL_HOST_USER = ''
#EMAIL_HOST_PASSWORD = ''
#EMAIL_USE_TLS = False
EMAIL_TIMEOUT = 10
SYSTEM_EMAIL_FROM = 'no-reply@example.com'
SYSTEM_EMAIL_ADMIN = 'admin@example.com'
ADMINS = [('Example', 'admin@example.com')]
HARVEST_SCRIPTS = ['harvest.arxiv']

LANGUAGE_CODE = 'en'

TIME_ZONE = 'Europe/Prague'

STATIC_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')
MEDIA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
