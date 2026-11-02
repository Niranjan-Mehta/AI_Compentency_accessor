from django.contrib import admin
from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'skill', 'batch_names', 'created_by', 'status', 'due_date')
    list_filter = ('status',)
    search_fields = ('title', 'skill')

    @admin.display(description='Batches')
    def batch_names(self, obj):
        return ', '.join(obj.batches.values_list('name', flat=True))
