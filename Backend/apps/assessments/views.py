from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import User
from apps.accounts.pagination import StandardResultsSetPagination

from .models import GeneratedQuestion
from .serializers import StaffQuestionSerializer, TraineeQuestionSerializer


class GeneratedQuestionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        queryset = GeneratedQuestion.objects.filter(
            assessment_run__status='COMPLETED',
        ).select_related('submission', 'competency_criterion').order_by('submission_id', 'display_order')
        if user.is_superuser:
            pass
        elif user.role == User.Role.TRAINEE:
            queryset = queryset.filter(submission__trainee=user)
        elif user.role == User.Role.FACULTY:
            queryset = queryset.filter(submission__task__batches__faculty=user)
        elif user.role == User.Role.TA:
            queryset = queryset.filter(submission__task__batches__tas=user)
        else:
            return queryset.none()

        submission_id = self.request.query_params.get('submission_id')
        if submission_id:
            if not submission_id.isdigit():
                raise ValidationError({'submission_id': 'Must be a positive integer.'})
            queryset = queryset.filter(submission_id=submission_id)
        return queryset.distinct()

    def get_serializer_class(self):
        if self.request.user.is_superuser or self.request.user.role != User.Role.TRAINEE:
            return StaffQuestionSerializer
        return TraineeQuestionSerializer
