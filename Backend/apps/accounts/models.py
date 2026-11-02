from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    class Role(models.TextChoices):
        FACULTY = 'FACULTY', 'Faculty'
        TA = 'TA', 'Teaching Assistant'
        TRAINEE = 'TRAINEE', 'Trainee'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.TRAINEE
    )

    employee_id = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.username} ({self.role})"