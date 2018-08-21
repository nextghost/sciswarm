from django.conf.urls import url, include

urlpatterns = [
    url(r'^', include('core.urls', namespace='core')),
]

handler400 = 'core.views.utils.bad_request'
handler403 = 'core.views.utils.permission_denied'
handler404 = 'core.views.utils.not_found'
handler405 = 'core.views.utils.method_not_allowed'
handler500 = 'core.views.utils.internal_error'
