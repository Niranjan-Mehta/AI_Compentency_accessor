from django.conf import settings
from django.db import models


class AssessmentRun(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    class ReviewStatus(models.TextChoices):
        NOT_RUN = 'NOT_RUN', 'Not run'
        SKIPPED = 'SKIPPED', 'Skipped'
        SUCCEEDED = 'SUCCEEDED', 'Succeeded'
        FAILED = 'FAILED', 'Failed'

    submission = models.OneToOneField(
        'submissions.Submission',
        on_delete=models.CASCADE,
        related_name='assessment_run',
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    error = models.TextField(blank=True, default='')
    opencode_review_status = models.CharField(
        max_length=16,
        choices=ReviewStatus.choices,
        default=ReviewStatus.NOT_RUN,
    )
    opencode_review_error = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'Assessment run for submission {self.submission_id} ({self.status})'


class OpenCodeReviewFinding(models.Model):
    assessment_run = models.ForeignKey(
        AssessmentRun,
        on_delete=models.CASCADE,
        related_name='opencode_findings',
    )
    file_path = models.CharField(max_length=500)
    start_line = models.PositiveIntegerField(null=True, blank=True)
    end_line = models.PositiveIntegerField(null=True, blank=True)
    severity = models.CharField(max_length=32, blank=True, default='')
    category = models.CharField(max_length=64, blank=True, default='')
    description = models.TextField()
    existing_code = models.TextField(blank=True, default='')
    suggestion_code = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['file_path', 'start_line', 'id']

    def __str__(self):
        return f'{self.file_path}:{self.start_line or "?"} ({self.severity or "unrated"})'


class GeneratedQuestion(models.Model):
    class Difficulty(models.TextChoices):
        EASY = 'EASY', 'Easy'
        MEDIUM = 'MEDIUM', 'Medium'
        HARD = 'HARD', 'Hard'

    submission = models.ForeignKey(
        'submissions.Submission',
        on_delete=models.CASCADE,
        related_name='generated_questions',
    )
    assessment_run = models.ForeignKey(
        AssessmentRun,
        on_delete=models.CASCADE,
        related_name='questions',
    )
    question_text = models.TextField()
    competency_criterion = models.ForeignKey(
        'rubrics.Criterion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_questions',
    )
    difficulty = models.CharField(max_length=8, choices=Difficulty.choices)
    code_file = models.CharField(max_length=500, null=True, blank=True)
    code_line = models.PositiveIntegerField(null=True, blank=True)
    code_snippet = models.TextField(blank=True, default='')
    expected_answer_points = models.JSONField(default=list)
    display_order = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['assessment_run', 'display_order'],
                name='unique_question_order_per_assessment_run',
            ),
        ]

    def __str__(self):
        return f'Question {self.display_order} for submission {self.submission_id}'


class AnswerSubmission(models.Model):
    """One answer set for a generated assessment run."""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SUBMITTED = 'SUBMITTED', 'Submitted'
        EVALUATING = 'EVALUATING', 'Evaluating'
        EVALUATED = 'EVALUATED', 'Evaluated'
        FAILED = 'FAILED', 'Failed'

    class ReviewStatus(models.TextChoices):
        NOT_STARTED = 'NOT_STARTED', 'Not started'
        IN_REVIEW = 'IN_REVIEW', 'In review'
        REVIEWED = 'REVIEWED', 'Reviewed'

    assessment_run = models.OneToOneField(
        AssessmentRun,
        on_delete=models.CASCADE,
        related_name='answer_submission',
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    evaluation_error = models.TextField(blank=True, default='')
    submitted_at = models.DateTimeField(null=True, blank=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)
    review_status = models.CharField(
        max_length=16,
        choices=ReviewStatus.choices,
        default=ReviewStatus.NOT_STARTED,
    )
    overall_ai_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    overall_final_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    overall_ai_level = models.CharField(max_length=2, blank=True, default='')
    overall_final_level = models.CharField(max_length=2, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'Answers for assessment run {self.assessment_run_id} ({self.status})'


class TraineeAnswer(models.Model):
    answer_submission = models.ForeignKey(
        AnswerSubmission,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    question = models.ForeignKey(
        GeneratedQuestion,
        on_delete=models.CASCADE,
        related_name='trainee_answers',
    )
    answer_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['question__display_order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['answer_submission', 'question'],
                name='unique_answer_per_question_submission',
            ),
        ]

    def __str__(self):
        return f'Answer to question {self.question_id}'


class QuestionEvaluation(models.Model):
    answer = models.OneToOneField(
        TraineeAnswer,
        on_delete=models.CASCADE,
        related_name='evaluation',
    )
    criterion = models.ForeignKey(
        'rubrics.Criterion',
        on_delete=models.PROTECT,
        related_name='question_evaluations',
    )
    score = models.DecimalField(max_digits=8, decimal_places=2)
    max_score = models.PositiveIntegerField()
    explanation = models.TextField()
    evidence = models.JSONField(default=list)
    strengths = models.JSONField(default=list)
    missing_points = models.JSONField(default=list)
    recommendations = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CriterionAssessment(models.Model):
    class Level(models.TextChoices):
        L1 = 'L1', 'Beginner'
        L2 = 'L2', 'Developing'
        L3 = 'L3', 'Proficient'
        L4 = 'L4', 'Advanced'

    answer_submission = models.ForeignKey(
        AnswerSubmission,
        on_delete=models.CASCADE,
        related_name='criterion_assessments',
    )
    criterion = models.ForeignKey(
        'rubrics.Criterion',
        on_delete=models.PROTECT,
        related_name='criterion_assessments',
    )
    ai_score = models.DecimalField(max_digits=8, decimal_places=2)
    final_score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    max_score = models.PositiveIntegerField()
    weight = models.DecimalField(max_digits=5, decimal_places=2)
    ai_level = models.CharField(max_length=2, choices=Level.choices)
    final_level = models.CharField(max_length=2, choices=Level.choices, blank=True, default='')
    override_reason = models.TextField(blank=True, default='')
    overridden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='criterion_score_overrides',
    )
    overridden_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['criterion_id']
        constraints = [
            models.UniqueConstraint(
                fields=['answer_submission', 'criterion'],
                name='unique_criterion_assessment_per_answer_submission',
            ),
        ]

    @property
    def effective_score(self):
        return self.final_score if self.final_score is not None else self.ai_score

    @property
    def effective_level(self):
        return self.final_level or self.ai_level
