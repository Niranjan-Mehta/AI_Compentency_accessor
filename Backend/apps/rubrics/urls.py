from rest_framework.routers import DefaultRouter

from .views import RubricViewSet


router = DefaultRouter()
router.register('rubrics', RubricViewSet, basename='rubric')

urlpatterns = router.urls
