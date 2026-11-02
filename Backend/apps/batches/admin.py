from django.contrib import admin

from .models import Batch


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'faculty', 'is_active', 'start_date', 'end_date', 'created_at')
    search_fields = ('name',)
    list_filter = ('is_active',)
    filter_horizontal = ('trainees', 'tas')
