import secrets

from django.conf import settings
from django.db import transaction
from django.core.mail import send_mail
from django.db.models import Q
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.audit.services import log as audit_log
from apps.batches.models import Batch

from .models import User
from .pagination import StandardResultsSetPagination
from .serializers import (
    InviteUserSerializer,
    ProfileSerializer,
    RoleTokenObtainPairSerializer,
    UserCreateSerializer,
    UserSerializer,
)
from .permissions import IsFaculty


class RoleTokenObtainPairView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer


class CreateUserView(APIView):
    permission_classes = [IsAuthenticated, IsFaculty]

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            user = serializer.save()
            return Response(
                UserSerializer(user).data,
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ProfileSerializer(request.user).data)

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, *, partial):
        serializer = ProfileSerializer(
            request.user,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UserListView(ListAPIView):
    """Faculty can browse users attached to their batches; superusers can browse all."""

    permission_classes = [IsAuthenticated, IsFaculty]
    serializer_class = UserSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = User.objects.all().order_by('last_name', 'first_name', 'username')
        batch_id = self.request.query_params.get('batch_id')
        if self.request.user.is_superuser:
            if batch_id:
                queryset = queryset.filter(
                    Q(batches__id=batch_id) | Q(ta_batches__id=batch_id)
                ).distinct()
        else:
            from apps.batches.models import Batch

            batches = Batch.objects.filter(faculty=self.request.user)
            if batch_id:
                batches = batches.filter(pk=batch_id)
                if not batches.exists():
                    return User.objects.none()
            queryset = queryset.filter(
                Q(batches__in=batches) | Q(ta_batches__in=batches)
            ).distinct()

        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(employee_id__icontains=search)
            )
        return queryset


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')

            if not refresh_token:
                return Response(
                    {"error": "Refresh token required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response({"message": "Logged out successfully"})

        except Exception:
            return Response(
                {"error": "Invalid refresh token"},
                status=status.HTTP_400_BAD_REQUEST
            )


class InviteUserView(APIView):
    permission_classes = [IsAuthenticated, IsFaculty]

    def post(self, request):
        serializer = InviteUserSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        batch = None
        batch_id = data.get('batch_id')
        if batch_id is not None:
            try:
                batch = Batch.objects.get(pk=batch_id)
            except Batch.DoesNotExist:
                return Response(
                    {'batch_id': ['Batch not found.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not request.user.is_superuser and batch.faculty_id != request.user.id:
                return Response(
                    {'detail': 'You can only invite users to batches you manage.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        username = data.get('username') or data['email'].split('@')[0]
        if User.objects.filter(username=username).exists():
            username = f'{username}_{secrets.token_hex(3)}'

        password = data.get('password') or secrets.token_urlsafe(12)
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=data['email'],
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', ''),
                role=data['role'],
                employee_id=data.get('employee_id'),
                password=password,
            )

            if batch is not None:
                if user.role == User.Role.TRAINEE:
                    batch.trainees.add(user)
                elif user.role == User.Role.TA:
                    batch.tas.add(user)

            audit_log(
                action='user-invited',
                actor=request.user,
                target=user.username,
                batch=batch,
                details={
                    'role': user.role,
                    'email': user.email,
                    'batch_id': batch.id if batch else None,
                },
            )
            if data.get('send_email', True):
                send_mail(
                    subject='Competency Assessor invitation',
                    message=(
                        f'You have been invited as {user.role}.\n'
                        f'Username: {user.username}\n'
                        f'Temporary password: {password}\n'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )

        payload = UserSerializer(user).data
        return Response(payload, status=status.HTTP_201_CREATED)
