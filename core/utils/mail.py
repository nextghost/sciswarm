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
