from django.conf.urls.defaults import *
from django.conf import settings
import os

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    (r'^insanity/', include('web.insanityweb.urls')),
    (r'^admin/', include(admin.site.urls)))


# DO NOT USE IN PRODUCTION.
# See django documentation about serving static files.
if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^site_media/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}),
    )
