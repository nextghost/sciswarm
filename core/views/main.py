from django.conf import settings
from django.shortcuts import render

def homepage(request):
    context = dict(admin_email=settings.SYSTEM_EMAIL_ADMIN)
    return render(request, 'core/main/homepage.html', context)
