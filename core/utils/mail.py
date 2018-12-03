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

from django.conf import settings
from django.core import mail
from django.template.loader import render_to_string
from .utils import logger

def send_mail(*args, **kwargs):
    kwargs.setdefault('from_email', settings.SYSTEM_EMAIL_FROM)
    try:
        return mail.send_mail(*args, **kwargs)
    except:
        logger.error('Error sending e-mail', exc_info=True)
    return 0

def send_template_mail(request, subject, template, context, recipient_list,
    **kwargs):
    text = render_to_string(template + '.txt', context, request).strip()
    html = render_to_string(template + '.html', context, request)
    kwargs['html_message'] = html
    kwargs['recipient_list'] = recipient_list
    return send_mail(subject, text, **kwargs)
