#!/usr/bin/python3
# When running this directly as a script, run it from the parent directory.
import django
import os

if __name__ == '__main__':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sciswarm.settings")
    django.setup()
    from django.apps import apps
    app_list = apps.get_app_configs()
    for item in app_list:
        if hasattr(item, 'run_cron'):
            item.run_cron()
