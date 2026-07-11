from django.urls import re_path as url
from django.contrib import admin

urlpatterns = [
    url(r'^admin/', admin.site.urls),
]
