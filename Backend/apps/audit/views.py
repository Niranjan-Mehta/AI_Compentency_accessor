from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import User
from apps.accounts.pagination import StandardResultsSetPagination
from .models import AuditEvent
from .serializers import AuditEventSerializer


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditEventSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        queryset = AuditEvent.objects.select_related('actor', 'batch')
        if user.is_superuser:
            pass
        elif user.role == User.Role.FACULTY:
            queryset = queryset.filter(batch__faculty=user) | queryset.filter(actor=user, batch__isnull=True)
        elif user.role == User.Role.TA:
            queryset = queryset.filter(batch__tas=user)
        else:
            raise PermissionDenied('Audit events are available to Faculty, TAs and administrators only.')
        batch_id = self.request.query_params.get('batch_id')
        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)
        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action__icontains=action)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(target__icontains=search) | queryset.filter(action__icontains=search)
        return queryset.distinct().order_by('-created_at')
