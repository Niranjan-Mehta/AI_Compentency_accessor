from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/', include('apps.batches.urls')),
    path('api/', include('apps.rubrics.urls')),
    path('api/', include('apps.tasks.urls')),
    path('api/', include('apps.submissions.urls')),
    path('api/', include('apps.assessments.urls')),
    path('api/', include('apps.reports.urls')),
    path('api/', include('apps.audit.urls')),
]
