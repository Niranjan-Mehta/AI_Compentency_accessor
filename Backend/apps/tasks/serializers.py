from rest_framework import serializers

from apps.batches.models import Batch
from apps.rubrics.models import Rubric
from apps.rubrics.serializers import RubricSerializer

from .models import Task


class BatchRelationField(serializers.PrimaryKeyRelatedField):
    def use_pk_only_optimization(self):
        return False

    def to_representation(self, value):
        return {'id': value.pk, 'name': value.name}


class RubricRelationField(serializers.PrimaryKeyRelatedField):
    def use_pk_only_optimization(self):
        return False

    def to_representation(self, value):
        return RubricSerializer(value, context=self.context).data


class TaskSerializer(serializers.ModelSerializer):
    skill = serializers.CharField(max_length=150, allow_blank=False, required=True)
    rubric = RubricRelationField(
        queryset=Rubric.objects.all(), required=True, allow_null=False,
    )
    batches = BatchRelationField(
        queryset=Batch.objects.all(),
        many=True,
        allow_empty=False,
        required=True,
    )
    questions_count = serializers.IntegerField(min_value=1, required=False)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'skill', 'due_date', 'status',
            'questions_count', 'require_pdf', 'allow_resubmission',
            'rubric', 'batches', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']

    def validate_rubric(self, rubric):
        request = self.context.get('request')
        if request and not request.user.is_superuser and rubric.created_by_id != request.user.id:
            raise serializers.ValidationError('You can only use rubrics you created.')
        return rubric

    def validate_batches(self, batches):
        request = self.context.get('request')
        if request and not request.user.is_superuser:
            invalid = [batch.id for batch in batches if batch.faculty_id != request.user.id]
            if invalid:
                raise serializers.ValidationError(
                    f'Tasks can only be assigned to your own batches: {invalid}.'
                )
        return batches
