from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'employee_id',
        ]


class ProfileSerializer(serializers.ModelSerializer):
    """Allow profile edits without allowing self-service role/ID changes."""

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'role',
            'employee_id',
        ]
        read_only_fields = ['id', 'username', 'role', 'employee_id']

    def validate_email(self, value):
        if value and User.objects.exclude(pk=self.instance.pk).filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'password',
            'role',
            'employee_id',
        ]

    def validate_employee_id(self, value):
        if value in (None, ''):
            return None
        return value

    def validate_role(self, value):
        request = self.context.get('request')
        if request and not request.user.is_superuser and value == User.Role.FACULTY:
            raise serializers.ValidationError('Only a superuser can create Faculty accounts.')
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        return User.objects.create_user(
            password=password,
            **validated_data
        )


class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    identifier = serializers.CharField(write_only=True, required=False)
    username = serializers.CharField(write_only=True, required=False)

    def validate(self, attrs):
        identifier = attrs.get('identifier') or attrs.get('username')
        if not identifier:
            raise serializers.ValidationError({'identifier': 'Enter your username, employee ID, or email.'})
        user = User.objects.filter(
            Q(username__iexact=identifier) | Q(email__iexact=identifier) | Q(employee_id=identifier),
        ).first()
        if user is None or not user.is_active or not user.check_password(attrs.get('password', '')):
            raise AuthenticationFailed('No active account found with the supplied credentials.')
        attrs['username'] = user.username
        attrs.pop('identifier', None)
        data = super().validate(attrs)
        self.user = user
        data['id'] = user.id
        data['username'] = user.username
        data['role'] = user.role
        data['employee_id'] = user.employee_id
        return data

class InviteUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=User.Role.choices)
    username = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True, default='')
    last_name = serializers.CharField(required=False, allow_blank=True, default='')
    employee_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(required=False, write_only=True, min_length=8)
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    send_email = serializers.BooleanField(required=False, default=True)

    def validate_role(self, value):
        request = self.context.get('request')
        if request and not request.user.is_superuser and value == User.Role.FACULTY:
            raise serializers.ValidationError('Only a superuser can invite Faculty accounts.')
        return value

    def validate(self, attrs):
        if not attrs.get('send_email', True) and not attrs.get('password'):
            raise serializers.ValidationError({
                'password': 'A password is required when invitation email is disabled.'
            })
        return attrs

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate_username(self, value):
        if value and User.objects.filter(username=value).exists():
            raise serializers.ValidationError('A user with this username already exists.')
        return value

    def validate_employee_id(self, value):
        if value in (None, ''):
            return None
        if User.objects.filter(employee_id=value).exists():
            raise serializers.ValidationError('A user with this employee ID already exists.')
        return value


