from django.conf import settings
from django.db import models


class Batch(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    faculty = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='managed_batches',
    )

    trainees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='batches',
        blank=True,
    )

    tas = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='ta_batches',
        blank=True,
    )

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
