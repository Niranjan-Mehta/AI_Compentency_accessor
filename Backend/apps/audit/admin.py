from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action', 'actor', 'actor_role', 'target', 'batch')
    list_filter = ('action', 'actor_role')
    search_fields = ('action', 'target')
    readonly_fields = (
        'actor',
        'actor_role',
        'action',
        'target',
        'batch',
        'details',
        'created_at',
    )
