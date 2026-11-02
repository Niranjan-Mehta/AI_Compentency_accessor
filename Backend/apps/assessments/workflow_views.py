from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.pagination import StandardResultsSetPagination
from apps.submissions.models import Submission

from .models import (
    AnswerSubmission,
    AssessmentRun,
    CriterionAssessment,
    GeneratedQuestion,
    QuestionEvaluation,
    TraineeAnswer,
)
from .services.evaluation import level_for_score, queue_evaluation, recalculate_totals
from .serializers import TraineeQuestionSerializer
from .workflow_serializers import (
    AnswerInputSerializer,
    AssessmentRunSummarySerializer,
    CriterionAssessmentSerializer,
    StaffQuestionEvaluationSerializer,
    TraineeQuestionEvaluationSerializer,
)


class AssessmentRunViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    serializer_class = AssessmentRunSummarySerializer

    def get_queryset(self):
        user = self.request.user
        queryset = AssessmentRun.objects.filter(status=AssessmentRun.Status.COMPLETED).select_related(
            'submission__trainee', 'submission__task',
        )
        if user.is_superuser:
            pass
        elif user.role == User.Role.TRAINEE:
            queryset = queryset.filter(submission__trainee=user)
        elif user.role == User.Role.FACULTY:
            queryset = queryset.filter(submission__task__batches__faculty=user)
        elif user.role == User.Role.TA:
            queryset = queryset.filter(submission__task__batches__tas=user)
        else:
            return queryset.none()
        batch_id = self.request.query_params.get('batch_id')
        if batch_id:
            if not batch_id.isdigit():
                raise ValidationError({'batch_id': 'Must be a positive integer.'})
            queryset = queryset.filter(submission__task__batches__id=batch_id)
        return queryset.distinct().order_by('-created_at', '-id')

    def _answer_submission(self, run, *, create=False):
        answer_submission = AnswerSubmission.objects.filter(assessment_run=run).first()
        if answer_submission is None and create:
            answer_submission, _ = AnswerSubmission.objects.get_or_create(assessment_run=run)
        return answer_submission

    @action(detail=True, methods=['get', 'post'], url_path='answers')
    def answers(self, request, pk=None):
        run = self.get_object()
        if request.method == 'POST':
            _require_trainee_owner(request.user, run.submission)
        answer_submission = self._answer_submission(run, create=request.method == 'POST')
        if request.method == 'GET':
            answer_by_question = {}
            if answer_submission is not None:
                answer_by_question = {
                    answer.question_id: answer
                    for answer in answer_submission.answers.select_related('question__competency_criterion').all()
                }
            questions = run.questions.select_related('competency_criterion').order_by('display_order', 'id')
            return Response({
                'assessment_run_id': run.id,
                'status': answer_submission.status if answer_submission else 'NOT_STARTED',
                'submitted_at': answer_submission.submitted_at if answer_submission else None,
                'questions': [
                    {
                        'question': TraineeQuestionSerializer(question).data,
                        'answer': {
                            'id': answer_by_question[question.id].id,
                            'answer_text': answer_by_question[question.id].answer_text,
                            'updated_at': answer_by_question[question.id].updated_at,
                        } if question.id in answer_by_question else None,
                    }
                    for question in questions
                ],
            })

        serializer = AnswerInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question_id = serializer.validated_data['question_id']
        question = get_object_or_404(
            GeneratedQuestion.objects.select_related('competency_criterion'),
            pk=question_id,
            assessment_run=run,
        )
        answer_submission = _save_answer(answer_submission, run, question, serializer.validated_data['answer_text'])
        answer = answer_submission.answers.get(question=question)
        return Response({
            'status': answer_submission.status,
            'answer': {
                'id': answer.id,
                'question_id': question.id,
                'answer_text': answer.answer_text,
                'updated_at': answer.updated_at,
            },
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='submit-answers')
    def submit_answers(self, request, pk=None):
        run = self.get_object()
        _require_trainee_owner(request.user, run.submission)
        answer_submission = self._answer_submission(run)
        if answer_submission is None:
            raise ValidationError({'answers': 'Save an answer for every question before submitting.'})
        questions = list(run.questions.values_list('id', flat=True))
        answer_ids = set(answer_submission.answers.values_list('question_id', flat=True))
        if not questions or answer_ids != set(questions):
            missing = sorted(set(questions) - answer_ids)
            raise ValidationError({'missing_question_ids': missing})
        if answer_submission.answers.filter(answer_text='').exists():
            raise ValidationError({'answers': 'Every answer must contain text.'})

        current = answer_submission.status
        if current in {AnswerSubmission.Status.SUBMITTED, AnswerSubmission.Status.EVALUATING}:
            return Response(_evaluation_status_payload(answer_submission, request.user), status=status.HTTP_202_ACCEPTED)
        if current == AnswerSubmission.Status.EVALUATED and not run.submission.task.allow_resubmission:
            return Response({'detail': 'Answers have already been submitted and evaluated.'}, status=status.HTTP_409_CONFLICT)
        if current == AnswerSubmission.Status.FAILED and not answer_submission.answers.exists():
            raise ValidationError({'answers': 'Save answers before retrying evaluation.'})

        with transaction.atomic():
            answer_submission = AnswerSubmission.objects.select_for_update().get(pk=answer_submission.pk)
            if answer_submission.status in {AnswerSubmission.Status.SUBMITTED, AnswerSubmission.Status.EVALUATING}:
                return Response(_evaluation_status_payload(answer_submission, request.user), status=status.HTTP_202_ACCEPTED)
            _clear_evaluation(answer_submission)
            answer_submission.status = AnswerSubmission.Status.SUBMITTED
            answer_submission.evaluation_error = ''
            answer_submission.submitted_at = timezone.now()
            answer_submission.evaluated_at = None
            answer_submission.review_status = AnswerSubmission.ReviewStatus.NOT_STARTED
            answer_submission.save(update_fields=[
                'status', 'evaluation_error', 'submitted_at', 'evaluated_at',
                'review_status', 'overall_ai_score', 'overall_final_score',
                'overall_ai_level', 'overall_final_level', 'updated_at',
            ])
        try:
            queue_evaluation(answer_submission.id)
        except Exception:
            answer_submission.status = AnswerSubmission.Status.FAILED
            answer_submission.evaluation_error = 'Evaluation could not be queued.'
            answer_submission.save(update_fields=['status', 'evaluation_error', 'updated_at'])
            return Response(_evaluation_status_payload(answer_submission, request.user), status=status.HTTP_503_SERVICE_UNAVAILABLE)
        answer_submission.refresh_from_db()
        return Response(_evaluation_status_payload(answer_submission, request.user), status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'], url_path='evaluation-status')
    def evaluation_status(self, request, pk=None):
        run = self.get_object()
        answer_submission = self._answer_submission(run)
        if answer_submission is None:
            return Response({'status': 'NOT_STARTED'})
        return Response(_evaluation_status_payload(answer_submission, request.user))

    @action(detail=True, methods=['get'], url_path='evaluation')
    def evaluation(self, request, pk=None):
        run = self.get_object()
        answer_submission = self._answer_submission(run)
        if answer_submission is None or answer_submission.status != AnswerSubmission.Status.EVALUATED:
            return Response({
                'status': answer_submission.status if answer_submission else 'NOT_STARTED',
                'detail': 'Evaluation results are not available yet.',
            }, status=status.HTTP_409_CONFLICT)
        evaluations = QuestionEvaluation.objects.filter(
            answer__answer_submission=answer_submission,
        ).select_related('answer__question', 'criterion').order_by('answer__question__display_order')
        criteria = answer_submission.criterion_assessments.select_related('criterion').all()
        is_trainee = request.user.role == User.Role.TRAINEE and not request.user.is_superuser
        question_serializer = TraineeQuestionEvaluationSerializer if is_trainee else StaffQuestionEvaluationSerializer
        criterion_serializer = _TraineeCriterionAssessmentSerializer if is_trainee else CriterionAssessmentSerializer
        return Response({
            'assessment_run_id': run.id,
            'status': answer_submission.status,
            'review_status': answer_submission.review_status,
            'overall_ai_score': answer_submission.overall_ai_score,
            'overall_final_score': answer_submission.overall_final_score,
            'overall_ai_level': answer_submission.overall_ai_level,
            'overall_final_level': answer_submission.overall_final_level,
            'evaluations': question_serializer(evaluations, many=True).data,
            'criteria': criterion_serializer(criteria, many=True).data,
        })

    @action(detail=True, methods=['get'], url_path='scores')
    def scores(self, request, pk=None):
        return self.evaluation(request, pk)

    @action(detail=True, methods=['post'], url_path='review')
    def review(self, request, pk=None):
        run = self.get_object()
        _require_ta_or_superuser(request.user)
        answer_submission = self._answer_submission(run)
        if answer_submission is None or answer_submission.status != AnswerSubmission.Status.EVALUATED:
            raise ValidationError({'status': 'Only evaluated assessments can be reviewed.'})
        review_status = request.data.get('status')
        if review_status not in {AnswerSubmission.ReviewStatus.IN_REVIEW, AnswerSubmission.ReviewStatus.REVIEWED}:
            raise ValidationError({'status': 'Choose IN_REVIEW or REVIEWED.'})
        answer_submission.review_status = review_status
        answer_submission.save(update_fields=['review_status', 'updated_at'])
        return Response({'assessment_run_id': run.id, 'review_status': review_status})

    @action(detail=True, methods=['post'], url_path=r'criteria/(?P<criterion_id>[^/.]+)/override')
    def override_criterion(self, request, pk=None, criterion_id=None):
        run = self.get_object()
        _require_ta_or_superuser(request.user)
        answer_submission = self._answer_submission(run)
        if answer_submission is None or answer_submission.status != AnswerSubmission.Status.EVALUATED:
            raise ValidationError({'status': 'Only evaluated assessments can be overridden.'})
        if answer_submission.review_status != AnswerSubmission.ReviewStatus.IN_REVIEW:
            raise ValidationError({'review_status': 'Set the assessment to IN_REVIEW before overriding scores.'})
        reason = request.data.get('reason')
        if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 2000:
            raise ValidationError({'reason': 'A reason of 1 to 2000 characters is required.'})
        raw_score = request.data.get('score')
        if isinstance(raw_score, bool):
            raise ValidationError({'score': 'Score must be numeric.'})
        try:
            score = Decimal(str(raw_score))
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError({'score': 'Score must be numeric.'})
        if not score.is_finite():
            raise ValidationError({'score': 'Score must be finite.'})
        criterion_assessment = get_object_or_404(
            CriterionAssessment.objects.select_related('criterion'),
            answer_submission=answer_submission,
            criterion_id=criterion_id,
        )
        if score < 0 or score > criterion_assessment.max_score:
            raise ValidationError({'score': f'Score must be between 0 and {criterion_assessment.max_score}.'})
        criterion_assessment.final_score = score.quantize(Decimal('0.01'))
        criterion_assessment.final_level = level_for_score(criterion_assessment.final_score, criterion_assessment.max_score)
        criterion_assessment.override_reason = reason.strip()
        criterion_assessment.overridden_by = request.user
        criterion_assessment.overridden_at = timezone.now()
        criterion_assessment.save(update_fields=[
            'final_score', 'final_level', 'override_reason', 'overridden_by', 'overridden_at', 'updated_at',
        ])
        recalculate_totals(answer_submission)
        return Response(CriterionAssessmentSerializer(criterion_assessment).data)


class AnswerDetailView(APIView):
    def put(self, request, run_id, question_id):
        return self._update(request, run_id, question_id)

    def patch(self, request, run_id, question_id):
        return self._update(request, run_id, question_id)

    def _update(self, request, run_id, question_id):
        run = _get_accessible_run(request.user, run_id)
        _require_trainee_owner(request.user, run.submission)
        serializer = AnswerInputSerializer(data={**request.data, 'question_id': question_id})
        serializer.is_valid(raise_exception=True)
        question = get_object_or_404(GeneratedQuestion, assessment_run=run, pk=question_id)
        answer_submission = AnswerSubmission.objects.filter(assessment_run=run).first()
        answer_submission = _save_answer(
            answer_submission, run, question, serializer.validated_data['answer_text'],
        )
        answer = answer_submission.answers.get(question=question)
        return Response({
            'status': answer_submission.status,
            'answer': {
                'id': answer.id,
                'question_id': question.id,
                'answer_text': answer.answer_text,
                'updated_at': answer.updated_at,
            },
        })


def _save_answer(answer_submission, run, question, answer_text):
    if len(answer_text) > 10000:
        raise ValidationError({'answer_text': 'Answers may not exceed 10000 characters.'})
    if answer_submission is None:
        answer_submission, _ = AnswerSubmission.objects.get_or_create(assessment_run=run)
    if answer_submission.status in {AnswerSubmission.Status.SUBMITTED, AnswerSubmission.Status.EVALUATING}:
        raise ValidationError({'status': 'Answers cannot be changed while evaluation is pending or running.'})
    if answer_submission.status in {AnswerSubmission.Status.EVALUATED, AnswerSubmission.Status.FAILED}:
        if not run.submission.task.allow_resubmission:
            raise ValidationError({'status': 'This task does not allow answer resubmission.'})
        with transaction.atomic():
            answer_submission = AnswerSubmission.objects.select_for_update().get(pk=answer_submission.pk)
            _clear_evaluation(answer_submission)
            answer_submission.status = AnswerSubmission.Status.DRAFT
            answer_submission.evaluation_error = ''
            answer_submission.submitted_at = None
            answer_submission.evaluated_at = None
            answer_submission.review_status = AnswerSubmission.ReviewStatus.NOT_STARTED
            answer_submission.save(update_fields=[
                'status', 'evaluation_error', 'submitted_at', 'evaluated_at', 'review_status',
                'overall_ai_score', 'overall_final_score', 'overall_ai_level',
                'overall_final_level', 'updated_at',
            ])
    TraineeAnswer.objects.update_or_create(
        answer_submission=answer_submission,
        question=question,
        defaults={'answer_text': answer_text},
    )
    return answer_submission


def _clear_evaluation(answer_submission):
    QuestionEvaluation.objects.filter(answer__answer_submission=answer_submission).delete()
    CriterionAssessment.objects.filter(answer_submission=answer_submission).delete()
    answer_submission.overall_ai_score = None
    answer_submission.overall_final_score = None
    answer_submission.overall_ai_level = ''
    answer_submission.overall_final_level = ''


def _get_accessible_run(user, run_id):
    queryset = AssessmentRun.objects.filter(status=AssessmentRun.Status.COMPLETED).select_related(
        'submission__trainee', 'submission__task',
    )
    if user.is_superuser:
        pass
    elif user.role == User.Role.TRAINEE:
        queryset = queryset.filter(submission__trainee=user)
    elif user.role == User.Role.FACULTY:
        queryset = queryset.filter(submission__task__batches__faculty=user)
    elif user.role == User.Role.TA:
        queryset = queryset.filter(submission__task__batches__tas=user)
    else:
        raise NotFound('Assessment not found.')
    run = queryset.distinct().filter(pk=run_id).first()
    if run is None:
        raise NotFound('Assessment not found.')
    return run


def _require_trainee_owner(user, submission):
    if user.is_superuser or user.role != User.Role.TRAINEE:
        raise PermissionDenied('Only the assigned trainee can submit answers.')
    if submission.trainee_id != user.id:
        raise NotFound('Assessment not found.')


def _require_ta_or_superuser(user):
    if not user.is_superuser and user.role != User.Role.TA:
        raise PermissionDenied('Only assigned TAs can review or override assessment scores.')


def _evaluation_status_payload(answer_submission, user):
    payload = {
        'assessment_run_id': answer_submission.assessment_run_id,
        'status': answer_submission.status,
        'submitted_at': answer_submission.submitted_at,
        'evaluated_at': answer_submission.evaluated_at,
    }
    if user.is_superuser or user.role != User.Role.TRAINEE:
        payload['error'] = answer_submission.evaluation_error
        payload['review_status'] = answer_submission.review_status
    elif answer_submission.status == AnswerSubmission.Status.FAILED:
        payload['error'] = 'Evaluation failed. Please contact your TA.'
    return payload


class _TraineeCriterionAssessmentSerializer(CriterionAssessmentSerializer):
    class Meta(CriterionAssessmentSerializer.Meta):
        fields = ['criterion_id', 'criterion_name', 'score', 'max_score', 'weight', 'level']
