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

from babel import Locale
from babel.dates import get_timezone_location, get_timezone
from django.conf import settings
from django.utils import timezone, translation
import pytz

TIMEZONE_SESSION_KEY = 'system_timezone'

def timezone_choices():
    lang = translation.get_language() or settings.LANGUAGE_CODE
    loc = Locale.parse(translation.to_locale(lang))
    tzlist = [(x, get_timezone_location(get_timezone(x), locale=loc))
        for x in pytz.common_timezones]
    # FIXME: Use locale-aware sorting
    return list(sorted(tzlist, key=lambda x: x[1]))

class TimezoneMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tzname = request.session.get(TIMEZONE_SESSION_KEY)
        if tzname:
            timezone.activate(tzname)
        else:
            timezone.deactivate()
        return self.get_response(request)
