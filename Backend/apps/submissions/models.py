import uuid

from django.conf import settings
from django.db import models


def submission_pdf_upload_to(instance, filename):
    # Ignore the client filename and generate a path entirely on the server.
    return f'submissions/pdfs/{instance.trainee_id}/{uuid.uuid4().hex}.pdf'


class Submission(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = 'SUBMITTED', 'Submitted'
        PROCESSING = 'PROCESSING', 'Processing'
        QUESTIONS_READY = 'QUESTIONS_READY', 'Questions ready'
        ANSWERS_SUBMITTED = 'ANSWERS_SUBMITTED', 'Answers submitted'
        UNDER_REVIEW = 'UNDER_REVIEW', 'Under review'
        PUBLISHED = 'PUBLISHED', 'Published'
        FAILED = 'FAILED', 'Failed'

    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.PROTECT,
        related_name='submissions',
    )
    repository_url = models.URLField(max_length=500)
    branch = models.CharField(max_length=255, default='main')
    commit_hash = models.CharField(max_length=64, null=True, blank=True)
    indexed_commit_hash = models.CharField(max_length=64, null=True, blank=True)
    processing_error = models.TextField(blank=True, default='')
    processed_at = models.DateTimeField(null=True, blank=True)
    project_pdf = models.FileField(
        upload_to=submission_pdf_upload_to,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )
    is_active = models.BooleanField(default=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['trainee', 'task'],
                condition=models.Q(is_active=True),
                name='one_active_submission_per_trainee_task',
            ),
        ]

    def __str__(self):
        return f'{self.trainee} - {self.task} ({self.status})'
