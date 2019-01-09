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

from django.core.exceptions import ValidationError
from django.db import models

class OpenChoiceField(models.CharField):
    # Don't validate value against self.choices
    def validate(self, value, instance):
        if not self.editable:
            return
        if value is None and not self.null:
            raise ValidationError(self.error_messages['null'], code='null')
        if not self.blank and value in self.empty_values:
            raise ValidationError(self.error_messages['blank'], code='blank')

