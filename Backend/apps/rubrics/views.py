from decimal import Decimal

from django.db.models import Prefetch
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.accounts.permissions import IsFaculty
from .models import CompetencyLevel, Rubric
from .serializers import RubricSerializer


class RubricViewSet(viewsets.ModelViewSet):
    serializer_class = RubricSerializer
    permission_classes = [IsFaculty]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        queryset = Rubric.objects.select_related('created_by').prefetch_related(
            'criteria',
            Prefetch('criteria__levels', queryset=CompetencyLevel.objects.order_by('level')),
        ).order_by('-updated_at', '-id')
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(created_by=self.request.user)

    def perform_destroy(self, instance):
        if instance.is_active:
            raise ValidationError('Only draft rubrics can be deleted.')
        if self._is_used(instance):
            raise ValidationError('A rubric assigned to a task cannot be deleted.')
        instance.delete()

    @staticmethod
    def _is_used(rubric):
        from apps.tasks.models import Task

        return Task.objects.filter(rubric=rubric, batches__isnull=False).exists()

    @staticmethod
    def _validate_for_activation(rubric):
        criteria = list(rubric.criteria.prefetch_related('levels'))
        if not criteria:
            raise ValidationError('A rubric must have at least one criterion before activation.')
        total_weight = sum((criterion.weight for criterion in criteria), Decimal('0'))
        if total_weight != Decimal('100'):
            raise ValidationError('Criterion weights must total 100 before activation.')

        expected_levels = {choice[0] for choice in CompetencyLevel.Level.choices}
        for criterion in criteria:
            actual_levels = {level.level for level in criterion.levels.all()}
            if actual_levels != expected_levels:
                raise ValidationError(
                    f'Criterion "{criterion.name}" must define L1, L2, L3, and L4.'
                )

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        rubric = self.get_object()
        if self._is_used(rubric):
            raise ValidationError('A rubric assigned to a task cannot be modified or activated.')
        self._validate_for_activation(rubric)
        if not rubric.is_active:
            rubric.is_active = True
            rubric.save(update_fields=['is_active', 'updated_at'])
        return Response(self.get_serializer(rubric).data)

    @action(detail=True, methods=['post'], permission_classes=[IsFaculty])
    def publish(self, request, pk=None):
        return self.activate(request, pk)
