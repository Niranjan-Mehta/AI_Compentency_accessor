from django.db import models
from django.conf import settings


class Rubric(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_rubrics'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def status(self):
        return 'ACTIVE' if self.is_active else 'DRAFT'

    @status.setter
    def status(self, value):
        self.is_active = value == 'ACTIVE'

    def __str__(self):
        return f"{self.name} (v{self.version})"


class Criterion(models.Model):
    rubric = models.ForeignKey(
        Rubric,
        on_delete=models.CASCADE,
        related_name='criteria'
    )

    name = models.CharField(max_length=150)
    description = models.TextField()

    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    max_score = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name


class CompetencyLevel(models.Model):

    class Level(models.TextChoices):
        L1 = 'L1', 'Beginner'
        L2 = 'L2', 'Developing'
        L3 = 'L3', 'Proficient'
        L4 = 'L4', 'Advanced'

    criterion = models.ForeignKey(
        Criterion,
        on_delete=models.CASCADE,
        related_name='levels'
    )

    level = models.CharField(
        max_length=2,
        choices=Level.choices
    )

    description = models.TextField()

    class Meta:
        unique_together = ('criterion', 'level')

    def __str__(self):
        return f"{self.criterion.name} - {self.level}"
