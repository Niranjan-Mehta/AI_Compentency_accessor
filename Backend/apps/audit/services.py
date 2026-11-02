from .models import AuditEvent


def log(*, action, actor=None, target='', batch=None, details=None):
    """Append an audit event. Safe to call from later phases."""
    actor_role = ''
    if actor is not None:
        actor_role = getattr(actor, 'role', '') or ''

    return AuditEvent.objects.create(
        actor=actor if getattr(actor, 'pk', None) else None,
        actor_role=actor_role,
        action=action,
        target=target or '',
        batch=batch,
        details=details or {},
    )
