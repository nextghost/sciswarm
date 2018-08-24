from django.utils import timezone
from .. import models

def delete_cancelled_accounts():
    query = (models.User.query_model.delete_deadline < timezone.now())
    models.User.objects.filter(query).delete()

def run_tasks():
    delete_cancelled_accounts()
