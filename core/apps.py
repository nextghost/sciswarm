from django.apps import AppConfig
from .utils import extmodels

class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        extmodels.create_query_model(self.get_models())

    def run_cron(self):
        from .utils import cron
        cron.run_tasks()
