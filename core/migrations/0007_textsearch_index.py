# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_paperimportsource'),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE INDEX core_paper_name_tsvec ON core_paper USING GIN (to_tsvector('english', name))",
            'DROP INDEX core_paper_name_tsvec'
        ),
        migrations.RunSQL(
            "CREATE INDEX core_paperauthorname_authorname_tsvec ON core_paperauthorname USING GIN (to_tsvector('simple', author_name))",
            'DROP INDEX core_paperauthorname_authorname_tsvec'
        ),
        migrations.AlterField(
            model_name='paperalias',
            name='identifier',
            field=models.CharField(db_index=True, max_length=256, verbose_name='identifier'),
        ),
        migrations.AlterField(
            model_name='personalias',
            name='identifier',
            field=models.CharField(db_index=True, max_length=150, verbose_name='identifier'),
        ),
    ]
