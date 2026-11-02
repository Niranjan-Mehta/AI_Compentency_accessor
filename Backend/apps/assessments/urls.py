from rest_framework.routers import DefaultRouter

from .views import GeneratedQuestionViewSet
from .workflow_views import AnswerDetailView, AssessmentRunViewSet
from django.urls import path


router = DefaultRouter()
router.register('questions', GeneratedQuestionViewSet, basename='generated-question')
router.register('assessment-runs', AssessmentRunViewSet, basename='assessment-run')

urlpatterns = [
    path(
        'assessment-runs/<int:run_id>/answers/<int:question_id>/',
        AnswerDetailView.as_view(),
        name='assessment-answer-detail',
    ),
] + router.urls
