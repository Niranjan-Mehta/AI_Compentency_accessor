from decimal import Decimal

from django.db.models import Prefetch, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import User
from apps.accounts.pagination import StandardResultsSetPagination
from apps.accounts.permissions import IsFaculty
from apps.rubrics.models import CompetencyLevel

from .models import Task
from .serializers import TaskSerializer


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'activate', 'complete'):
            return [IsFaculty()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        queryset = Task.objects.select_related('rubric', 'created_by').prefetch_related(
            'batches',
            'rubric__criteria',
            Prefetch('rubric__criteria__levels', queryset=CompetencyLevel.objects.order_by('level')),
        )
        if user.is_superuser:
            pass
        elif user.role == User.Role.FACULTY:
            queryset = queryset.filter(created_by=user)
        elif user.role == User.Role.TA:
            queryset = queryset.filter(batches__tas=user)
        elif user.role == User.Role.TRAINEE:
            queryset = queryset.filter(batches__trainees=user, status=Task.Status.ACTIVE)
        else:
            return queryset.none()

        if self.action == 'list':
            search = self.request.query_params.get('search')
            if search:
                queryset = queryset.filter(Q(title__icontains=search) | Q(skill__icontains=search))
        return queryset.distinct().order_by('-created_at', '-id')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        task = serializer.instance
        if task.status != Task.Status.DRAFT and not self.request.user.is_superuser:
            raise ValidationError('Only draft tasks can be updated.')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != Task.Status.DRAFT:
            raise ValidationError('Only draft tasks can be deleted.')
        instance.delete()

    @staticmethod
    def _validate_rubric_for_activation(task):
        rubric = task.rubric
        if rubric is None or not rubric.is_active:
            raise ValidationError('Activate the rubric before activating this task.')
        criteria = list(rubric.criteria.prefetch_related('levels'))
        if not criteria:
            raise ValidationError('The selected rubric must contain criteria.')
        if sum((criterion.weight for criterion in criteria), Decimal('0')) != Decimal('100'):
            raise ValidationError('The selected rubric criteria must total 100% weight.')
        expected_levels = {choice[0] for choice in CompetencyLevel.Level.choices}
        if any({level.level for level in criterion.levels.all()} != expected_levels for criterion in criteria):
            raise ValidationError('Every rubric criterion must define L1, L2, L3, and L4.')

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        task = self.get_object()
        if task.status != Task.Status.DRAFT:
            raise ValidationError('Only draft tasks can be activated.')
        if not task.batches.exists():
            raise ValidationError('Assign the task to at least one batch before activation.')
        self._validate_rubric_for_activation(task)
        task.status = Task.Status.ACTIVE
        task.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        task = self.get_object()
        if task.status != Task.Status.ACTIVE:
            raise ValidationError('Only active tasks can be completed.')
        task.status = Task.Status.COMPLETED
        task.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(task).data)

    @action(detail=False, methods=['get'], url_path='assigned-to-trainee')
    def assigned_to_trainee(self, request):
        if request.user.is_superuser:
            queryset = Task.objects.filter(status=Task.Status.ACTIVE)
        elif request.user.role == User.Role.TRAINEE:
            queryset = Task.objects.filter(
                batches__trainees=request.user,
                status=Task.Status.ACTIVE,
            )
        else:
            raise PermissionDenied('This endpoint is only available to trainees.')
        queryset = queryset.select_related('rubric').prefetch_related(
            'batches', 'rubric__criteria', 'rubric__criteria__levels',
        ).distinct().order_by('-created_at', '-id')
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='assigned-to-ta')
    def assigned_to_ta(self, request):
        if request.user.is_superuser:
            queryset = Task.objects.all()
        elif request.user.role == User.Role.TA:
            queryset = Task.objects.filter(batches__tas=request.user)
        else:
            raise PermissionDenied('This endpoint is only available to TAs.')
        queryset = queryset.select_related('rubric').prefetch_related(
            'batches', 'rubric__criteria', 'rubric__criteria__levels',
        ).distinct().order_by('-created_at', '-id')
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)
