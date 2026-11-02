from django.db import models
from django.conf import settings


class Task(models.Model):

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        ACTIVE = 'ACTIVE', 'Active'
        COMPLETED = 'COMPLETED', 'Completed'

    title = models.CharField(max_length=200)
    description = models.TextField()
    skill = models.CharField(max_length=150, blank=True, default='')

    rubric = models.ForeignKey(
        'rubrics.Rubric',
        on_delete=models.PROTECT,
        related_name='tasks',
        null=True,
        blank=True,
    )

    batches = models.ManyToManyField(
        'batches.Batch',
        related_name='tasks',
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_tasks'
    )

    due_date = models.DateTimeField(null=True, blank=True)
    questions_count = models.PositiveIntegerField(default=6)
    require_pdf = models.BooleanField(default=True)
    allow_resubmission = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
