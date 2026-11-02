from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        'username',
        'email',
        'employee_id',
        'role',
        'is_staff',
        'is_active',
    )
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'employee_id')
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Competency Assessor', {'fields': ('role', 'employee_id')}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ('Competency Assessor', {'fields': ('role', 'employee_id')}),
    )
