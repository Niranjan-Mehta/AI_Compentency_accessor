from django.db.models import Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsBatchManager, IsFaculty
from apps.accounts.pagination import StandardResultsSetPagination
from apps.accounts.serializers import UserSerializer
from apps.audit.services import log as audit_log

from .models import Batch
from .serializers import BatchSerializer, MembershipSerializer


class BatchViewSet(viewsets.ModelViewSet):
    serializer_class = BatchSerializer
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action == 'create':
            return [IsFaculty()]
        if self.action in ('update', 'partial_update', 'destroy'):
            return [IsFaculty(), IsBatchManager()]
        if self.action in ('trainees', 'tas') and self.request.method in ('POST', 'DELETE'):
            return [IsFaculty(), IsBatchManager()]
        return [IsBatchManager()]

    def get_queryset(self):
        user = self.request.user
        qs = Batch.objects.select_related('faculty').prefetch_related('tas').annotate(
            trainee_count=Count('trainees', distinct=True),
            ta_count=Count('tas', distinct=True),
        ).order_by('name', 'id')
        if user.is_superuser:
            pass
        elif user.role == User.Role.FACULTY:
            qs = qs.filter(faculty=user)
        elif user.role == User.Role.TA:
            qs = qs.filter(tas=user)
        elif user.role == User.Role.TRAINEE:
            qs = qs.filter(trainees=user)
        else:
            return qs.none()

        search = self.request.query_params.get('search')
        if self.action == 'list' and search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        return qs

    def perform_create(self, serializer):
        batch = serializer.save()
        audit_log(
            action='batch-created',
            actor=self.request.user,
            target=batch.name,
            batch=batch,
        )
        # Include the annotated roster counts in the creation response.
        serializer.instance = self.get_queryset().get(pk=batch.pk)

    def perform_update(self, serializer):
        changed_fields = sorted(serializer.validated_data.keys())
        batch = serializer.save()
        audit_log(
            action='batch-updated',
            actor=self.request.user,
            target=batch.name,
            batch=batch,
            details={'changed_fields': changed_fields},
        )

    def perform_destroy(self, instance):
        audit_log(
            action='batch-deleted',
            actor=self.request.user,
            target=instance.name,
            batch=instance,
        )
        instance.delete()

    def _membership_users(self, request, expected_role):
        serializer = MembershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_ids = serializer.validated_data['user_ids']
        users = list(User.objects.filter(pk__in=user_ids, role=expected_role))
        found_ids = {user.id for user in users}
        missing = [user_id for user_id in user_ids if user_id not in found_ids]
        if missing:
            return None, Response(
                {
                    'user_ids': [
                        f'Users not found or not {expected_role}: {missing}'
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return users, None

    def _filter_members(self, queryset):
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
                | Q(employee_id__icontains=search)
            )
        return queryset.order_by('first_name', 'last_name', 'username')

    def _member_response(self, queryset):
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(UserSerializer(page, many=True).data)
        return Response(UserSerializer(queryset, many=True).data)

    def _require_roster_access(self, request, batch):
        if request.user.is_superuser:
            return
        if request.user.role == User.Role.FACULTY:
            if batch.faculty_id == request.user.id:
                return
        elif request.user.role == User.Role.TA and batch.tas.filter(pk=request.user.pk).exists():
            return
        if request.user.role not in {User.Role.FACULTY, User.Role.TA}:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied('Only assigned staff can view batch rosters.')
        from rest_framework.exceptions import NotFound

        raise NotFound('Batch not found.')

    @action(detail=True, methods=['get', 'post', 'delete'])
    def trainees(self, request, pk=None):
        batch = self.get_object()
        if request.method == 'GET':
            self._require_roster_access(request, batch)
            members = self._filter_members(batch.trainees.all())
            return self._member_response(members)

        users, error = self._membership_users(request, User.Role.TRAINEE)
        if error:
            return error

        if request.method == 'POST':
            batch.trainees.add(*users)
            action_name = 'trainees-added'
        else:
            batch.trainees.remove(*users)
            action_name = 'trainees-removed'

        audit_log(
            action=action_name,
            actor=request.user,
            target=batch.name,
            batch=batch,
            details={'user_ids': [user.id for user in users]},
        )
        members = self._filter_members(batch.trainees.all())
        return self._member_response(members)

    @action(detail=True, methods=['get', 'post', 'delete'])
    def tas(self, request, pk=None):
        batch = self.get_object()
        if request.method == 'GET':
            self._require_roster_access(request, batch)
            members = self._filter_members(batch.tas.all())
            return self._member_response(members)

        users, error = self._membership_users(request, User.Role.TA)
        if error:
            return error

        if request.method == 'POST':
            batch.tas.add(*users)
            action_name = 'tas-added'
        else:
            batch.tas.remove(*users)
            action_name = 'tas-removed'

        audit_log(
            action=action_name,
            actor=request.user,
            target=batch.name,
            batch=batch,
            details={'user_ids': [user.id for user in users]},
        )
        members = self._filter_members(batch.tas.all())
        return self._member_response(members)
