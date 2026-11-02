from pathlib import PurePath

from django.conf import settings
from rest_framework import serializers

from apps.tasks.models import Task
from .models import Submission
from .repositories import get_repository_provider


class TaskSummaryField(serializers.PrimaryKeyRelatedField):
    def use_pk_only_optimization(self):
        return False

    def to_representation(self, task):
        return {
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'skill': task.skill,
            'due_date': task.due_date,
            'status': task.status,
        }


class SubmissionSerializer(serializers.ModelSerializer):
    task = TaskSummaryField(queryset=Task.objects.all(), required=True)
    trainee_id = serializers.IntegerField(source='trainee.id', read_only=True)
    trainee_name = serializers.SerializerMethodField()
    trainee_email = serializers.EmailField(source='trainee.email', read_only=True)
    project_pdf = serializers.FileField(
        write_only=True,
        required=False,
        allow_null=True,
    )
    branch = serializers.CharField(max_length=255, required=False, default='main')
    commit_hash = serializers.CharField(max_length=64, required=False, allow_blank=True, allow_null=True)
    status = serializers.CharField(read_only=True)
    submitted_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    has_pdf = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            'id', 'task', 'repository_url', 'branch', 'commit_hash', 'project_pdf',
            'status', 'submitted_at', 'updated_at', 'has_pdf', 'trainee_id',
            'trainee_name', 'trainee_email',
        ]
        read_only_fields = ['id', 'status', 'submitted_at', 'updated_at', 'has_pdf']

    def get_has_pdf(self, submission):
        return bool(submission.project_pdf)

    def get_trainee_name(self, submission):
        return submission.trainee.get_full_name() or submission.trainee.username

    def validate_repository_url(self, value):
        provider = get_repository_provider()
        try:
            return provider.validate_repository_url(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_project_pdf(self, uploaded_file):
        if uploaded_file is None:
            return None
        if uploaded_file.size > settings.MAX_SUBMISSION_PDF_SIZE:
            limit_mb = settings.MAX_SUBMISSION_PDF_SIZE // (1024 * 1024)
            raise serializers.ValidationError(f'PDF must be no larger than {limit_mb} MB.')
        if PurePath(uploaded_file.name).suffix.lower() != '.pdf':
            raise serializers.ValidationError('Only PDF files are accepted.')
        if uploaded_file.content_type != 'application/pdf':
            raise serializers.ValidationError('The uploaded file must have PDF MIME type.')

        current_position = uploaded_file.tell()
        signature = uploaded_file.read(5)
        uploaded_file.seek(current_position)
        if signature != b'%PDF-':
            raise serializers.ValidationError('The uploaded file does not have a valid PDF signature.')
        return uploaded_file

    def validate(self, attrs):
        task = attrs.get('task')
        if task is None and self.instance is not None:
            task = self.instance.task
        if task and task.require_pdf and not attrs.get('project_pdf'):
            raise serializers.ValidationError({'project_pdf': 'A PDF is required for this task.'})
        return attrs
