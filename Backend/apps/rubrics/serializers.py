from decimal import Decimal

from django.apps import apps
from django.db import transaction
from rest_framework import serializers

from .models import CompetencyLevel, Criterion, Rubric


LEVELS = {choice[0] for choice in CompetencyLevel.Level.choices}


class CompetencyLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompetencyLevel
        fields = ['level', 'description']


class CriterionSerializer(serializers.ModelSerializer):
    levels = CompetencyLevelSerializer(many=True)
    max_score = serializers.IntegerField(min_value=1)
    weight = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0'),
        max_value=Decimal('100'),
    )

    class Meta:
        model = Criterion
        fields = ['id', 'name', 'description', 'weight', 'max_score', 'levels']
        read_only_fields = ['id']

    def validate_levels(self, levels):
        supplied = [item['level'] for item in levels]
        if set(supplied) != LEVELS or len(supplied) != len(LEVELS):
            raise serializers.ValidationError('Provide one description for each level: L1, L2, L3, and L4.')
        return levels


class RubricStatusField(serializers.Field):
    default_error_messages = {'invalid': 'Status must be DRAFT or ACTIVE.'}

    def to_representation(self, value):
        return 'ACTIVE' if value else 'DRAFT'

    def to_internal_value(self, data):
        if data == 'ACTIVE':
            return True
        if data == 'DRAFT':
            return False
        self.fail('invalid')


class RubricSerializer(serializers.ModelSerializer):
    status = RubricStatusField(source='is_active', read_only=True)
    criteria = CriterionSerializer(many=True, required=False)

    class Meta:
        model = Rubric
        fields = ['id', 'name', 'description', 'status', 'created_at', 'updated_at', 'criteria']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _is_used_by_assigned_task(self):
        if not self.instance:
            return False
        Task = apps.get_model('tasks', 'Task')
        return Task.objects.filter(rubric=self.instance, batches__isnull=False).exists()

    def validate(self, attrs):
        if self.instance and self._is_used_by_assigned_task():
            raise serializers.ValidationError('A rubric used by an assigned task cannot be modified.')

        criteria = attrs.get('criteria')
        if self.instance is None and not criteria:
            raise serializers.ValidationError({'criteria': 'At least one criterion is required.'})
        if criteria is not None:
            total = sum((item['weight'] for item in criteria), Decimal('0'))
            if total != Decimal('100'):
                raise serializers.ValidationError({'criteria': 'Criterion weights must total 100.'})
        return attrs

    @staticmethod
    def _create_criteria(rubric, criteria_data):
        for item in criteria_data:
            levels_data = item.pop('levels')
            criterion = Criterion.objects.create(rubric=rubric, **item)
            CompetencyLevel.objects.bulk_create([
                CompetencyLevel(criterion=criterion, **level)
                for level in levels_data
            ])

    @transaction.atomic
    def create(self, validated_data):
        criteria_data = validated_data.pop('criteria')
        rubric = Rubric.objects.create(
            created_by=self.context['request'].user,
            **validated_data,
        )
        self._create_criteria(rubric, criteria_data)
        return rubric

    @transaction.atomic
    def update(self, instance, validated_data):
        criteria_data = validated_data.pop('criteria', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if criteria_data is not None:
            instance.criteria.all().delete()
            self._create_criteria(instance, criteria_data)
        return instance
