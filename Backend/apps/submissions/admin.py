from django.contrib import admin

from .models import Submission


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'trainee', 'task', 'status', 'is_active', 'submitted_at')
    list_filter = ('status', 'is_active')
    search_fields = ('trainee__username', 'task__title', 'repository_url')
    readonly_fields = ('submitted_at', 'updated_at')
