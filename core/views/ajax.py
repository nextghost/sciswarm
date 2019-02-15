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
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from .base import BaseListView
from .. import models

def science_subfields(request):
    field_id = request.GET.get('value')
    qs = models.ScienceSubfield.objects.all()
    if field_id is not None:
        query = (models.ScienceSubfield.query_model.field == field_id)
        qs = qs.filter(query)
    ret = [(x.pk, str(x)) for x in qs]
    return JsonResponse(ret, safe=False)
