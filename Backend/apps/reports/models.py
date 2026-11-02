from django.conf import settings
from django.db import models


class Report(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PUBLISHED = 'PUBLISHED', 'Published'

    assessment_run = models.ForeignKey(
        'assessments.AssessmentRun',
        on_delete=models.PROTECT,
        related_name='reports',
    )
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='assessment_reports',
    )
    task = models.ForeignKey('tasks.Task', on_delete=models.PROTECT, related_name='reports')
    batch = models.ForeignKey('batches.Batch', on_delete=models.PROTECT, related_name='reports')
    overall_score = models.DecimalField(max_digits=7, decimal_places=2)
    competency_level = models.CharField(max_length=2)
    snapshot = models.JSONField(default=dict)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='published_assessment_reports',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['assessment_run', 'batch'],
                name='unique_report_per_assessment_batch',
            ),
        ]

    def __str__(self):
        return f'{self.task.title} report for {self.trainee} ({self.status})'
