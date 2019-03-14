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

from . import sql
from .utils import fold_or
from ..models import const
from .. import models

# If person_id is not None, only reviews posted by people followed
# by the person (and the person's own review if any) will count
def paper_review_rating_subquery(paper_list=None, person_id=None):
    revtab = sql.Table(models.PaperReview)
    join = revtab
    where = (revtab.deleted == False)
    if isinstance(paper_list, (list, tuple)):
        where &= revtab.paper_id.belongs(paper_list)
    elif paper_list is not None:
        where &= (revtab.paper_id == paper_list)
    if person_id is not None:
        followtab = sql.Table(models.FeedSubscription)
        subtype = const.feed_subscription_types.REVIEWS
        cond = ((revtab.posted_by_id == followtab.poster_id) &
            (followtab.follower_id == person_id) &
            (followtab.subscription_type == subtype))
        join = join.left_join(followtab, cond)
        where &= ((revtab.posted_by_id == person_id) | followtab.pk.notnull())
    fields = [revtab.paper_id]
    # Multiply values by 50 to get percentage
    alias = dict(methodology_avg=sql.avg(50*revtab.methodology),
        methodology_sd=sql.stddev_pop(50*revtab.methodology),
        importance_avg=sql.avg(50*revtab.importance),
        importance_sd=sql.stddev_pop(50*revtab.importance),
        review_count=sql.count(revtab.pk))
    return join.select(*fields, alias=alias, where=where, group_by=fields)
