from django.db import transaction
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.pagination import StandardResultsSetPagination
from apps.tasks.models import Task

from .models import Submission
from .serializers import SubmissionSerializer
from .jobs import start_processing
from .vector_store import retrieve_chunks


class SubmissionViewSet(viewsets.ModelViewSet):
    serializer_class = SubmissionSerializer
    pagination_class = StandardResultsSetPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Submission.objects.select_related('trainee', 'task').prefetch_related('task__batches')
        if user.is_superuser:
            pass
        elif user.role == User.Role.TRAINEE:
            queryset = queryset.filter(trainee=user)
        elif user.role == User.Role.FACULTY:
            queryset = queryset.filter(task__batches__faculty=user)
        elif user.role == User.Role.TA:
            queryset = queryset.filter(task__batches__tas=user)
        else:
            return queryset.none()

        task_id = self.request.query_params.get('task_id')
        if task_id:
            if not task_id.isdigit():
                raise ValidationError({'task_id': 'Must be a positive integer.'})
            queryset = queryset.filter(task_id=task_id)

        batch_id = self.request.query_params.get('batch_id')
        if batch_id:
            if not batch_id.isdigit():
                raise ValidationError({'batch_id': 'Must be a positive integer.'})
            queryset = queryset.filter(task__batches__id=batch_id)

        submission_status = self.request.query_params.get('status')
        if submission_status:
            valid_statuses = {choice[0] for choice in Submission.Status.choices}
            if submission_status not in valid_statuses:
                raise ValidationError({'status': 'Invalid submission status.'})
            queryset = queryset.filter(status=submission_status)
        return queryset.distinct().order_by('-submitted_at', '-id')

    def create(self, request, *args, **kwargs):
        self._require_trainee(request.user)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.validated_data['task']
        self._validate_task_for_submission(task, request.user)

        with transaction.atomic():
            existing = Submission.objects.select_for_update().filter(
                trainee=request.user,
                task=task,
                is_active=True,
            ).first()
            if existing and not task.allow_resubmission:
                raise ValidationError('This task does not allow resubmission.')
            if existing:
                existing.is_active = False
                existing.save(update_fields=['is_active', 'updated_at'])
            submission = serializer.save(
                trainee=request.user,
                is_active=True,
                status=Submission.Status.SUBMITTED,
            )

        return Response(self.get_serializer(submission).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        return self._resubmit(request, partial=False, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        return self._resubmit(request, partial=True, **kwargs)

    def _resubmit(self, request, *, partial, **kwargs):
        submission = self.get_object()
        self._require_trainee_owner(request.user, submission)
        if not submission.is_active:
            raise ValidationError('Only the active submission can be updated.')
        task = submission.task
        if not task.allow_resubmission:
            raise ValidationError('This task does not allow resubmission.')
        self._validate_task_for_submission(task, request.user)

        serializer = self.get_serializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        submitted_task = serializer.validated_data.get('task', task)
        if submitted_task.id != task.id:
            raise ValidationError({'task': 'A resubmission must remain attached to the same task.'})

        values = serializer.validated_data
        repository_url = values.get('repository_url', submission.repository_url)
        branch = values.get('branch', submission.branch)
        commit_hash = values.get('commit_hash', submission.commit_hash)
        project_pdf = values.get('project_pdf', submission.project_pdf)
        if task.require_pdf and not values.get('project_pdf'):
            raise ValidationError({'project_pdf': 'A PDF is required for each resubmission.'})

        with transaction.atomic():
            submission.is_active = False
            submission.save(update_fields=['is_active', 'updated_at'])
            replacement = Submission.objects.create(
                trainee=request.user,
                task=task,
                repository_url=repository_url,
                branch=branch,
                commit_hash=commit_hash,
                project_pdf=project_pdf,
                status=Submission.Status.SUBMITTED,
                is_active=True,
            )
        return Response(self.get_serializer(replacement).data)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        submission = self.get_object()
        if not submission.project_pdf:
            raise NotFound('This submission has no PDF.')
        return FileResponse(
            submission.project_pdf.open('rb'),
            as_attachment=True,
            filename=f'submission-{submission.id}.pdf',
            content_type='application/pdf',
        )

    @action(detail=True, methods=['post'], url_path='process')
    def process(self, request, pk=None):
        submission = self.get_object()
        self._require_processor(request.user)
        if submission.status == Submission.Status.PROCESSING:
            return Response({'id': submission.id, 'status': submission.status}, status=status.HTTP_202_ACCEPTED)
        start_processing(submission)
        return Response(
            {'id': submission.id, 'status': Submission.Status.PROCESSING},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=['get'], url_path='processing-status')
    def processing_status(self, request, pk=None):
        submission = self.get_object()
        return Response({
            'id': submission.id,
            'status': submission.status,
            'commit_hash': submission.commit_hash,
            'processed_at': submission.processed_at,
            'error': submission.processing_error,
        })

    @action(detail=True, methods=['post'], url_path='retrieve')
    def query_context(self, request, pk=None):
        submission = self.get_object()
        query = request.data.get('query', '')
        if not isinstance(query, str) or not query.strip():
            raise ValidationError({'query': 'A non-empty query is required.'})
        source_type = request.data.get('source_type')
        try:
            results = retrieve_chunks(
                submission,
                query,
                source_type=source_type,
                limit=request.data.get('limit', 5),
            )
        except (ValueError, TypeError) as exc:
            raise ValidationError({'detail': str(exc)}) from exc
        return Response({'submission_id': submission.id, 'results': results})

    @action(detail=True, methods=['post'], url_path='generate-questions')
    def generate_questions(self, request, pk=None):
        submission = self.get_object()
        self._require_processor(request.user)
        if submission.status != Submission.Status.QUESTIONS_READY or not submission.indexed_commit_hash:
            raise ValidationError('Submission must be processed and indexed before question generation.')

        from apps.assessments.models import AssessmentRun
        from apps.assessments.services.question_generation import queue_question_generation

        run, _ = AssessmentRun.objects.get_or_create(submission=submission)
        if run.status == AssessmentRun.Status.COMPLETED:
            return Response({'assessment_run_id': run.id, 'status': run.status})
        if run.status == AssessmentRun.Status.PROCESSING:
            return Response({'assessment_run_id': run.id, 'status': run.status}, status=status.HTTP_202_ACCEPTED)

        with transaction.atomic():
            run = AssessmentRun.objects.select_for_update().get(pk=run.pk)
            if run.status == AssessmentRun.Status.COMPLETED:
                return Response({'assessment_run_id': run.id, 'status': run.status})
            if run.status != AssessmentRun.Status.PROCESSING:
                run.status = AssessmentRun.Status.PROCESSING
                run.error = ''
                run.opencode_review_status = AssessmentRun.ReviewStatus.NOT_RUN
                run.opencode_review_error = ''
                run.save(update_fields=[
                    'status', 'error', 'opencode_review_status', 'opencode_review_error', 'updated_at',
                ])

        try:
            queue_question_generation(run.id)
        except Exception:
            run.status = AssessmentRun.Status.FAILED
            run.error = 'Question generation could not be queued.'
            run.save(update_fields=['status', 'error', 'updated_at'])
            return Response(
                {'assessment_run_id': run.id, 'status': run.status, 'error': run.error},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {'assessment_run_id': run.id, 'status': AssessmentRun.Status.PROCESSING},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=['get'], url_path='generation-status')
    def generation_status(self, request, pk=None):
        submission = self.get_object()
        from apps.assessments.models import AssessmentRun

        run = AssessmentRun.objects.filter(submission=submission).first()
        if run is None:
            return Response({'status': 'NOT_STARTED'})
        response = {
            'assessment_run_id': run.id,
            'status': run.status,
            'updated_at': run.updated_at,
        }
        if request.user.is_superuser or request.user.role != User.Role.TRAINEE:
            response['error'] = run.error
        return Response(response)

    @action(detail=True, methods=['get'], url_path='questions')
    def questions(self, request, pk=None):
        submission = self.get_object()
        from apps.assessments.models import AssessmentRun, GeneratedQuestion
        from apps.assessments.serializers import StaffQuestionSerializer, TraineeQuestionSerializer

        run = AssessmentRun.objects.filter(submission=submission).first()
        if run is None or run.status != AssessmentRun.Status.COMPLETED:
            return Response({'status': run.status if run else 'NOT_STARTED', 'results': []})
        serializer_class = (
            TraineeQuestionSerializer
            if request.user.role == User.Role.TRAINEE and not request.user.is_superuser
            else StaffQuestionSerializer
        )
        questions = GeneratedQuestion.objects.filter(assessment_run=run).select_related('competency_criterion')
        return Response({
            'assessment_run_id': run.id,
            'status': run.status,
            'results': serializer_class(questions, many=True).data,
        })

    @staticmethod
    def _require_trainee(user):
        if user.is_superuser or user.role != User.Role.TRAINEE:
            raise PermissionDenied('Only trainees can submit project work.')

    @classmethod
    def _require_trainee_owner(cls, user, submission):
        cls._require_trainee(user)
        if submission.trainee_id != user.id:
            raise NotFound('Submission not found.')

    @staticmethod
    def _require_processor(user):
        if user.is_superuser:
            return
        # The viewset queryset already confines trainees to their own submissions.
        if user.role not in {User.Role.FACULTY, User.Role.TA, User.Role.TRAINEE}:
            raise PermissionDenied('Only an assigned trainee, TA, or faculty can process submissions.')

    @staticmethod
    def _validate_task_for_submission(task, trainee):
        if task.status != Task.Status.ACTIVE:
            raise ValidationError({'task': 'Only active tasks accept submissions.'})
        if not task.batches.filter(trainees=trainee).exists():
            raise PermissionDenied('You are not assigned to this task.')
        if task.due_date and timezone.now() > task.due_date:
            raise ValidationError({'task': 'The task due date has passed.'})
