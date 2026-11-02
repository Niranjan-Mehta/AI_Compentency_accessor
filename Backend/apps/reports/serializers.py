from rest_framework import serializers

from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    trainee_id = serializers.IntegerField(read_only=True)
    trainee_name = serializers.SerializerMethodField()
    task_id = serializers.IntegerField(read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)
    batch_id = serializers.IntegerField(read_only=True)
    batch_name = serializers.CharField(source='batch.name', read_only=True)

    class Meta:
        model = Report
        fields = [
            'id', 'assessment_run_id', 'trainee_id', 'trainee_name', 'task_id', 'task_title',
            'batch_id', 'batch_name', 'overall_score', 'competency_level', 'status',
            'published_at', 'published_by', 'snapshot', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_trainee_name(self, report):
        return report.trainee.get_full_name() or report.trainee.username
