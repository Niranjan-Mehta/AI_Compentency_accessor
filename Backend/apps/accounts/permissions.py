from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsFaculty(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return (
            user.is_authenticated
            and (user.is_superuser or user.role == 'FACULTY')
        )


class IsTA(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return (
            user.is_authenticated
            and (user.is_superuser or user.role == 'TA')
        )


class IsTrainee(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return (
            user.is_authenticated
            and (user.is_superuser or user.role == 'TRAINEE')
        )


class IsFacultyOrTA(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return (
            user.is_authenticated
            and (
                user.is_superuser
                or user.role in ['FACULTY', 'TA']
            )
        )


class IsBatchManager(BasePermission):
    """Read if the user belongs to the batch; write only for owning faculty."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True

        if request.method in SAFE_METHODS:
            return (
                obj.faculty_id == user.id
                or obj.trainees.filter(pk=user.pk).exists()
                or obj.tas.filter(pk=user.pk).exists()
            )

        return user.role == 'FACULTY' and obj.faculty_id == user.id