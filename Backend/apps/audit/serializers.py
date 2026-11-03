from rest_framework import serializers

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = ['id', 'actor_name', 'actor_role', 'action', 'target', 'batch_id', 'details', 'created_at']

    def get_actor_name(self, event):
        return event.actor.get_full_name() or event.actor.username if event.actor_id else 'System'
