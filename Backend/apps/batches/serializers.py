from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer

from .models import Batch


class MembershipSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )


class BatchSerializer(serializers.ModelSerializer):
    faculty = UserSerializer(read_only=True)
    tas = UserSerializer(many=True, read_only=True)
    trainee_count = serializers.IntegerField(read_only=True)
    ta_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Batch
        fields = [
            'id',
            'name',
            'description',
            'faculty',
            'tas',
            'trainee_count',
            'ta_count',
            'start_date',
            'end_date',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def create(self, validated_data):
        request = self.context['request']
        return Batch.objects.create(faculty=request.user, **validated_data)
