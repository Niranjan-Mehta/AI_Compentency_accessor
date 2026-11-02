from django.contrib import admin
from .models import Rubric, Criterion, CompetencyLevel


class CompetencyLevelInline(admin.TabularInline):
    model = CompetencyLevel
    extra = 4


class CriterionInline(admin.TabularInline):
    model = Criterion
    extra = 1


@admin.register(Rubric)
class RubricAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'created_by', 'updated_at')
    inlines = [CriterionInline]


@admin.register(Criterion)
class CriterionAdmin(admin.ModelAdmin):
    list_display = ('name', 'rubric', 'weight', 'max_score')
    inlines = [CompetencyLevelInline]
