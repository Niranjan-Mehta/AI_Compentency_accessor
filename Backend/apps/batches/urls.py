from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BatchViewSet

router = DefaultRouter()
router.register('batches', BatchViewSet, basename='batch')

urlpatterns = [
    path('', include(router.urls)),
]
