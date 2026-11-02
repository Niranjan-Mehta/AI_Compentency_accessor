from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.pagination import StandardResultsSetPagination
from apps.assessments.models import AnswerSubmission, AssessmentRun, QuestionEvaluation
from apps.batches.models import Batch

from .models import Report
from .serializers import ReportSerializer


class ReportViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ReportSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        queryset = Report.objects.select_related(
            'assessment_run', 'trainee', 'task', 'batch', 'published_by',
        )
        if user.is_superuser:
            pass
        elif user.role == User.Role.TRAINEE:
            queryset = queryset.filter(trainee=user, status=Report.Status.PUBLISHED)
        elif user.role == User.Role.FACULTY:
            queryset = queryset.filter(batch__faculty=user)
        elif user.role == User.Role.TA:
            queryset = queryset.filter(batch__tas=user)
        else:
            return queryset.none()
        batch_id = self.request.query_params.get('batch_id')
        if batch_id:
            if not batch_id.isdigit() or int(batch_id) < 1:
                raise ValidationError({'batch_id': 'Must be a positive integer.'})
            queryset = queryset.filter(batch_id=batch_id)
        status_filter = self.request.query_params.get('status')
        if status_filter in Report.Status.values and user.role != User.Role.TRAINEE:
            queryset = queryset.filter(status=status_filter)
        return queryset.distinct().order_by('-created_at', '-id')

    @action(detail=False, methods=['post'], url_path='prepare')
    def prepare(self, request):
        _require_faculty(request.user)
        run_id = request.data.get('assessment_run_id')
        if isinstance(run_id, bool) or not str(run_id or '').isdigit() or int(run_id) < 1:
            raise ValidationError({'assessment_run_id': 'A positive assessment run ID is required.'})
        run = AssessmentRun.objects.select_related(
            'submission__trainee', 'submission__task',
        ).filter(pk=run_id, status=AssessmentRun.Status.COMPLETED).first()
        if run is None:
            raise NotFound('Completed assessment not found.')
        if not request.user.is_superuser and not run.submission.task.batches.filter(faculty=request.user).exists():
            raise NotFound('Completed assessment not found.')

        answer_submission = AnswerSubmission.objects.filter(assessment_run=run).first()
        if answer_submission is None or answer_submission.status != AnswerSubmission.Status.EVALUATED:
            raise ValidationError({'assessment': 'An assessment must be fully evaluated before report preparation.'})
        if answer_submission.review_status != AnswerSubmission.ReviewStatus.REVIEWED:
            raise ValidationError({'review_status': 'TA review must be completed before preparing this report.'})
        if not answer_submission.criterion_assessments.exists():
            raise ValidationError({'assessment': 'The evaluation has no complete criterion scores.'})
        rubric_criterion_count = run.submission.task.rubric.criteria.count() if run.submission.task.rubric_id else 0
        if answer_submission.criterion_assessments.count() != rubric_criterion_count:
            raise ValidationError({'assessment': 'The evaluation does not cover every rubric criterion.'})
        if answer_submission.overall_final_score is None or answer_submission.overall_final_level not in {'L1', 'L2', 'L3', 'L4'}:
            raise ValidationError({'assessment': 'The evaluation has no final competency score.'})
        question_count = run.questions.count()
        if question_count != run.submission.task.questions_count or answer_submission.answers.count() != question_count:
            raise ValidationError({'assessment': 'The assessment does not contain an answer for every configured question.'})
        evaluation_count = QuestionEvaluation.objects.filter(
            answer__answer_submission=answer_submission,
        ).count()
        if evaluation_count != answer_submission.answers.count():
            raise ValidationError({'assessment': 'The evaluation is incomplete.'})

        batches = Batch.objects.filter(
            tasks=run.submission.task,
            trainees=run.submission.trainee,
        )
        if not request.user.is_superuser:
            batches = batches.filter(faculty=request.user)
        batches = list(batches.order_by('id'))
        if not batches:
            raise ValidationError({'batch': 'The trainee is not a member of an assigned batch managed by this faculty.'})

        prepared = []
        created_any = False
        with transaction.atomic():
            for batch in batches:
                snapshot = _build_snapshot(run, answer_submission, batch)
                report, created = Report.objects.get_or_create(
                    assessment_run=run,
                    batch=batch,
                    defaults={
                        'trainee': run.submission.trainee,
                        'task': run.submission.task,
                        'overall_score': answer_submission.overall_final_score,
                        'competency_level': answer_submission.overall_final_level,
                        'snapshot': snapshot,
                    },
                )
                created_any = created_any or created
                if report.status != Report.Status.PUBLISHED:
                    report.trainee = run.submission.trainee
                    report.task = run.submission.task
                    report.overall_score = answer_submission.overall_final_score
                    report.competency_level = answer_submission.overall_final_level
                    report.snapshot = snapshot
                    report.save(update_fields=[
                        'trainee', 'task', 'overall_score', 'competency_level', 'snapshot', 'updated_at',
                    ])
                prepared.append(report)
        response_status = status.HTTP_201_CREATED if created_any else status.HTTP_200_OK
        return Response(ReportSerializer(prepared, many=True).data, status=response_status)

    @action(detail=True, methods=['post'], url_path='publish')
    def publish(self, request, pk=None):
        _require_faculty(request.user)
        report = self.get_object()
        if report.status == Report.Status.PUBLISHED:
            return Response(self.get_serializer(report).data)
        run = report.assessment_run
        answer_submission = AnswerSubmission.objects.filter(assessment_run=run).first()
        if (
            run.status != AssessmentRun.Status.COMPLETED
            or answer_submission is None
            or answer_submission.status != AnswerSubmission.Status.EVALUATED
            or answer_submission.review_status != AnswerSubmission.ReviewStatus.REVIEWED
        ):
            raise ValidationError('Only complete, TA-reviewed assessments can be published.')
        if report.snapshot.get('source_updated_at') != answer_submission.updated_at.isoformat():
            raise ValidationError('Assessment data changed after this report was prepared. Prepare it again before publishing.')
        report.status = Report.Status.PUBLISHED
        report.published_at = timezone.now()
        report.published_by = request.user
        report.save(update_fields=['status', 'published_at', 'published_by', 'updated_at'])
        return Response(self.get_serializer(report).data)


def _require_faculty(user):
    if not user.is_superuser and user.role != User.Role.FACULTY:
        raise PermissionDenied('Only faculty can prepare or publish reports.')


def _build_snapshot(run, answer_submission, batch):
    submission = run.submission
    criterion_scores = list(answer_submission.criterion_assessments.select_related(
        'criterion', 'overridden_by',
    ).order_by('criterion_id'))
    evaluations = list(QuestionEvaluation.objects.filter(
        answer__answer_submission=answer_submission,
    ).select_related('answer__question', 'criterion').order_by('answer__question__display_order'))

    criteria = []
    for score in criterion_scores:
        criterion_feedback = [item for item in evaluations if item.criterion_id == score.criterion_id]
        criteria.append({
            'criterion_id': score.criterion_id,
            'name': score.criterion.name,
            'weight': str(score.weight),
            'score': str(score.effective_score),
            'ai_score': str(score.ai_score),
            'max_score': score.max_score,
            'level': score.effective_level,
            'ai_level': score.ai_level,
            'feedback': [_evaluation_snapshot(item) for item in criterion_feedback],
            'override_reason': score.override_reason,
            'overridden_by': score.overridden_by.get_full_name() or score.overridden_by.username
            if score.overridden_by else None,
            'overridden_at': score.overridden_at.isoformat() if score.overridden_at else None,
        })

    return {
        'task': {'id': submission.task_id, 'title': submission.task.title, 'skill': submission.task.skill},
        'trainee': {
            'id': submission.trainee_id,
            'name': submission.trainee.get_full_name() or submission.trainee.username,
            'employee_id': submission.trainee.employee_id,
        },
        'batch': {'id': batch.id, 'name': batch.name},
        'assessment_run_id': run.id,
        'submission_id': submission.id,
        'overall_score': str(answer_submission.overall_final_score),
        'ai_overall_score': str(answer_submission.overall_ai_score),
        'competency_level': answer_submission.overall_final_level,
        'ai_competency_level': answer_submission.overall_ai_level,
        'criteria': criteria,
        'ta_review': {
            'status': answer_submission.review_status,
            'overrides': [
                {
                    'criterion_id': score.criterion_id,
                    'criterion': score.criterion.name,
                    'reason': score.override_reason,
                    'reviewer': score.overridden_by.get_full_name() or score.overridden_by.username
                    if score.overridden_by else None,
                    'reviewed_at': score.overridden_at.isoformat() if score.overridden_at else None,
                }
                for score in criterion_scores if score.final_score is not None
            ],
        },
        'source_updated_at': answer_submission.updated_at.isoformat(),
        'prepared_at': timezone.now().isoformat(),
    }


def _evaluation_snapshot(evaluation):
    question = evaluation.answer.question
    return {
        'question_id': question.id,
        'question': question.question_text,
        'score': str(evaluation.score),
        'max_score': evaluation.max_score,
        'explanation': evaluation.explanation,
        'evidence': evaluation.evidence,
        'strengths': evaluation.strengths,
        'missing_points': evaluation.missing_points,
        'recommendations': evaluation.recommendations,
    }
