import json
from decimal import Decimal
from unittest.mock import Mock, patch

from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.assessments.models import (
    AnswerSubmission,
    AssessmentRun,
    CriterionAssessment,
    GeneratedQuestion,
    QuestionEvaluation,
    TraineeAnswer,
)
from apps.batches.models import Batch
from apps.rubrics.models import CompetencyLevel, Criterion, Rubric
from apps.submissions.models import Submission
from apps.tasks.models import Task
from apps.assessments.services.evaluation import evaluate_answer_submission
from apps.assessments.services.question_generation import generate_questions

from .models import Report


def mocked_question_payload(criterion_id):
    types = ['IMPLEMENTATION', 'IMPLEMENTATION', 'DESIGN', 'DECISION', 'DEBUGGING', 'DESIGN']
    return json.dumps({'questions': [{
        'question_text': f'How does this project implement behavior {index}, and why?',
        'question_type': question_type,
        'competency_criterion_id': criterion_id,
        'difficulty': 'MEDIUM',
        'code_file': 'src/calculate.py',
        'code_line': 1,
        'code_snippet': 'def calculate(value):',
        'expected_answer_points': ['Describe the implementation choice.'],
    } for index, question_type in enumerate(types, start=1)]})


class ReportPublishingTests(APITestCase):
    def setUp(self):
        self.faculty = User.objects.create(username='report-faculty', role=User.Role.FACULTY)
        self.other_faculty = User.objects.create(username='other-report-faculty', role=User.Role.FACULTY)
        self.ta = User.objects.create(username='report-ta', role=User.Role.TA)
        self.trainee = User.objects.create(username='report-trainee', role=User.Role.TRAINEE)
        self.other_trainee = User.objects.create(username='other-report-trainee', role=User.Role.TRAINEE)
        self.batch = Batch.objects.create(name='Report batch', faculty=self.faculty)
        self.batch.trainees.add(self.trainee)
        self.batch.tas.add(self.ta)
        self.rubric = Rubric.objects.create(name='Report rubric', created_by=self.faculty)
        self.criterion = Criterion.objects.create(
            rubric=self.rubric,
            name='Implementation',
            description='Quality of implementation.',
            weight='100.00',
            max_score=100,
        )
        CompetencyLevel.objects.bulk_create([
            CompetencyLevel(criterion=self.criterion, level=level, description=f'{level} performance')
            for level in ('L1', 'L2', 'L3', 'L4')
        ])
        self.task = Task.objects.create(
            title='Report workflow task',
            description='Explain this implementation.',
            skill='Backend',
            created_by=self.faculty,
            rubric=self.rubric,
            questions_count=1,
        )
        self.task.batches.add(self.batch)
        self.submission = Submission.objects.create(
            trainee=self.trainee,
            task=self.task,
            repository_url='https://code.example.org/team/report-task',
            status=Submission.Status.QUESTIONS_READY,
            indexed_commit_hash='c' * 40,
        )
        self.run = AssessmentRun.objects.create(
            submission=self.submission,
            status=AssessmentRun.Status.COMPLETED,
        )
        self.answer_submission = AnswerSubmission.objects.create(
            assessment_run=self.run,
            status=AnswerSubmission.Status.EVALUATED,
            review_status=AnswerSubmission.ReviewStatus.REVIEWED,
            overall_ai_score=Decimal('72.00'),
            overall_final_score=Decimal('78.00'),
            overall_ai_level='L3',
            overall_final_level='L4',
        )
        self.question = GeneratedQuestion.objects.create(
            submission=self.submission,
            assessment_run=self.run,
            question_text='Explain how the service handles invalid input and why.',
            competency_criterion=self.criterion,
            difficulty=GeneratedQuestion.Difficulty.MEDIUM,
            display_order=1,
            expected_answer_points=['Private scoring guidance.'],
        )
        self.answer = TraineeAnswer.objects.create(
            answer_submission=self.answer_submission,
            question=self.question,
            answer_text='The service checks the input before processing it.',
        )
        self.question_evaluation = QuestionEvaluation.objects.create(
            answer=self.answer,
            criterion=self.criterion,
            score=Decimal('72.00'),
            max_score=100,
            explanation='The trainee described the validation path and its purpose.',
            evidence=[{'source_type': 'CODE', 'file_path': 'service.py', 'start_line': 4, 'end_line': 6}],
            strengths=['Explained the validation path.'],
            missing_points=['Could discuss an edge case.'],
            recommendations=['Explain the error response behavior.'],
        )
        CriterionAssessment.objects.create(
            answer_submission=self.answer_submission,
            criterion=self.criterion,
            ai_score=Decimal('72.00'),
            final_score=Decimal('78.00'),
            max_score=100,
            weight=Decimal('100.00'),
            ai_level='L3',
            final_level='L4',
            override_reason='The oral response showed additional understanding.',
            overridden_by=self.ta,
        )

    def prepare(self):
        return self.client.post('/api/reports/prepare/', {'assessment_run_id': self.run.id}, format='json')

    def test_faculty_prepares_and_publishes_immutable_snapshot(self):
        self.client.force_authenticate(self.faculty)
        prepared = self.prepare()
        self.assertEqual(prepared.status_code, 201, prepared.data)
        self.assertEqual(len(prepared.data), 1)
        report = Report.objects.get(assessment_run=self.run, batch=self.batch)
        self.assertEqual(report.status, Report.Status.DRAFT)
        self.assertEqual(report.overall_score, Decimal('78.00'))
        self.assertEqual(report.competency_level, 'L4')
        self.assertEqual(report.snapshot['criteria'][0]['feedback'][0]['explanation'], self.question_evaluation.explanation)
        self.assertEqual(report.snapshot['ta_review']['overrides'][0]['reason'], 'The oral response showed additional understanding.')

        published = self.client.post(f'/api/reports/{report.id}/publish/')
        self.assertEqual(published.status_code, 200, published.data)
        report.refresh_from_db()
        original_snapshot = report.snapshot
        self.assertEqual(report.status, Report.Status.PUBLISHED)
        self.assertEqual(report.published_by, self.faculty)
        self.assertIsNotNone(report.published_at)

        CriterionAssessment.objects.filter(answer_submission=self.answer_submission).update(final_score=Decimal('10.00'))
        refreshed = self.prepare()
        self.assertEqual(refreshed.status_code, 200)
        report.refresh_from_db()
        self.assertEqual(report.snapshot, original_snapshot)
        self.assertEqual(report.overall_score, Decimal('78.00'))

    def test_ta_can_review_but_cannot_prepare_or_publish(self):
        self.client.force_authenticate(self.ta)
        forbidden_prepare = self.prepare()
        self.assertEqual(forbidden_prepare.status_code, 403)

        self.client.force_authenticate(self.faculty)
        report_id = self.prepare().data[0]['id']
        self.client.force_authenticate(self.ta)
        self.assertEqual(self.client.get('/api/reports/').data['count'], 1)
        self.assertEqual(self.client.get(f'/api/reports/{report_id}/').status_code, 200)
        self.assertEqual(self.client.post(f'/api/reports/{report_id}/publish/').status_code, 403)

    def test_trainee_sees_only_own_published_reports(self):
        self.client.force_authenticate(self.faculty)
        report_id = self.prepare().data[0]['id']
        self.client.force_authenticate(self.trainee)
        self.assertEqual(self.client.get('/api/reports/').data['count'], 0)
        self.assertEqual(self.client.get(f'/api/reports/{report_id}/').status_code, 404)

        self.client.force_authenticate(self.faculty)
        self.client.post(f'/api/reports/{report_id}/publish/')
        self.client.force_authenticate(self.trainee)
        reports = self.client.get('/api/reports/')
        self.assertEqual(reports.status_code, 200)
        self.assertEqual(reports.data['count'], 1)
        self.assertEqual(self.client.get(f'/api/reports/{report_id}/').status_code, 200)
        self.assertNotIn('Private scoring guidance.', str(reports.data))

        self.client.force_authenticate(self.other_trainee)
        self.assertEqual(self.client.get(f'/api/reports/{report_id}/').status_code, 404)
        self.assertEqual(self.client.get('/api/reports/').data['count'], 0)

    def test_report_cannot_be_prepared_without_completed_ta_review_or_full_evaluation(self):
        self.client.force_authenticate(self.faculty)
        self.answer_submission.review_status = AnswerSubmission.ReviewStatus.IN_REVIEW
        self.answer_submission.save(update_fields=['review_status'])
        needs_review = self.prepare()
        self.assertEqual(needs_review.status_code, 400)
        self.assertFalse(Report.objects.exists())

        self.answer_submission.review_status = AnswerSubmission.ReviewStatus.REVIEWED
        self.answer_submission.status = AnswerSubmission.Status.FAILED
        self.answer_submission.save(update_fields=['review_status', 'status'])
        incomplete = self.prepare()
        self.assertEqual(incomplete.status_code, 400)
        self.assertFalse(Report.objects.exists())

    def test_report_access_is_scoped_to_faculty_batches(self):
        self.client.force_authenticate(self.other_faculty)
        self.assertEqual(self.prepare().status_code, 404)

        self.client.force_authenticate(self.faculty)
        report_id = self.prepare().data[0]['id']
        self.client.force_authenticate(self.other_faculty)
        self.assertEqual(self.client.get(f'/api/reports/{report_id}/').status_code, 404)

    def test_incomplete_answers_cannot_be_prepared_and_changed_draft_must_be_reprepared(self):
        self.client.force_authenticate(self.faculty)
        self.answer.delete()
        incomplete = self.prepare()
        self.assertEqual(incomplete.status_code, 400)
        self.assertFalse(Report.objects.exists())

        self.answer = TraineeAnswer.objects.create(
            answer_submission=self.answer_submission,
            question=self.question,
            answer_text='The service validates its input before continuing.',
        )
        self.question_evaluation.answer = self.answer
        self.question_evaluation.save()
        prepared = self.prepare()
        self.assertEqual(prepared.status_code, 201)
        report_id = prepared.data[0]['id']
        self.answer_submission.refresh_from_db()
        self.answer_submission.save(update_fields=['updated_at'])
        stale_publish = self.client.post(f'/api/reports/{report_id}/publish/')
        self.assertEqual(stale_publish.status_code, 400)


class MockedWorkflowEndToEndTests(APITestCase):
    """Cross-role API workflow with external AI and repository work mocked."""

    def setUp(self):
        self.faculty = User.objects.create(username='e2e-faculty', role=User.Role.FACULTY)
        self.ta = User.objects.create(username='e2e-ta', role=User.Role.TA)
        self.trainee = User.objects.create(username='e2e-trainee', role=User.Role.TRAINEE)
        self.code_chunk = {'content': 'def calculate(value):\n    return value * 2\n', 'metadata': {
            'source_type': 'CODE', 'file_path': 'src/calculate.py', 'start_line': 1, 'end_line': 2,
        }}
        self.pdf_chunk = {'content': 'The project doubles a value before returning it.', 'metadata': {
            'source_type': 'PDF', 'file_path': 'explanation.pdf', 'page': 1,
        }}

    def test_trainee_to_ta_to_faculty_to_published_trainee_workflow(self):
        self.client.force_authenticate(self.faculty)
        batch_response = self.client.post('/api/batches/', {'name': 'E2E batch'}, format='json')
        self.assertEqual(batch_response.status_code, 201, batch_response.data)
        self.batch = Batch.objects.get(pk=batch_response.data['id'])
        self.assertEqual(self.client.post(
            f'/api/batches/{self.batch.id}/trainees/', {'user_ids': [self.trainee.id]}, format='json',
        ).status_code, 200)
        self.assertEqual(self.client.post(
            f'/api/batches/{self.batch.id}/tas/', {'user_ids': [self.ta.id]}, format='json',
        ).status_code, 200)

        rubric_response = self.client.post('/api/rubrics/', {
            'name': 'E2E rubric', 'description': 'Workflow rubric.', 'criteria': [{
                'name': 'Implementation', 'description': 'Technical correctness.',
                'weight': '100.00', 'max_score': 100,
                'levels': [{'level': level, 'description': f'{level} quality'} for level in ('L1', 'L2', 'L3', 'L4')],
            }],
        }, format='json')
        self.assertEqual(rubric_response.status_code, 201, rubric_response.data)
        self.rubric = Rubric.objects.get(pk=rubric_response.data['id'])
        self.criterion = self.rubric.criteria.get()
        self.assertEqual(self.client.post(f'/api/rubrics/{self.rubric.id}/activate/').status_code, 200)
        task_response = self.client.post('/api/tasks/', {
            'title': 'E2E task', 'description': 'Explain an implementation.', 'skill': 'Backend',
            'rubric': self.rubric.id, 'batches': [self.batch.id], 'questions_count': 6,
            'require_pdf': False,
        }, format='json')
        self.assertEqual(task_response.status_code, 201, task_response.data)
        self.task = Task.objects.get(pk=task_response.data['id'])
        self.assertEqual(self.client.post(f'/api/tasks/{self.task.id}/activate/').status_code, 200)

        self.client.force_authenticate(self.trainee)
        submission_response = self.client.post('/api/submissions/', {
            'task': self.task.id, 'repository_url': 'https://code.example.org/team/e2e', 'branch': 'main',
        }, format='json')
        self.assertEqual(submission_response.status_code, 201, submission_response.data)
        self.submission = Submission.objects.get(pk=submission_response.data['id'])
        with patch('apps.submissions.views.start_processing', return_value=True):
            started = self.client.post(f'/api/submissions/{self.submission.id}/process/')
        self.assertEqual(started.status_code, 202)
        self.submission.status = Submission.Status.QUESTIONS_READY
        self.submission.indexed_commit_hash = 'd' * 40
        self.submission.save(update_fields=['status', 'indexed_commit_hash', 'updated_at'])

        with patch('apps.assessments.services.question_generation.queue_question_generation', return_value=True):
            queued = self.client.post(f'/api/submissions/{self.submission.id}/generate-questions/')
        self.assertEqual(queued.status_code, 202)
        run = AssessmentRun.objects.get(submission=self.submission)
        generation_provider = Mock()
        generation_provider.generate.return_value = mocked_question_payload(self.criterion.id)
        with (
            patch('apps.assessments.services.question_generation.retrieve_chunks', side_effect=[[self.code_chunk], [self.pdf_chunk]]),
            patch('apps.assessments.services.question_generation.get_llm_provider', return_value=generation_provider),
        ):
            generate_questions(run.id)
        questions = list(run.questions.order_by('display_order'))
        self.assertEqual(len(questions), 6)
        self.assertEqual(self.client.get(f'/api/submissions/{self.submission.id}/questions/').data['status'], AssessmentRun.Status.COMPLETED)

        for question in questions:
            response = self.client.post(
                f'/api/assessment-runs/{run.id}/answers/',
                {'question_id': question.id, 'answer_text': 'The function doubles its input and returns the result.'},
                format='json',
            )
            self.assertEqual(response.status_code, 200)
        with patch('apps.assessments.services.evaluation.queue_evaluation', return_value=True):
            submitted = self.client.post(f'/api/assessment-runs/{run.id}/submit-answers/')
        self.assertEqual(submitted.status_code, 202)
        answer_submission = AnswerSubmission.objects.get(assessment_run=run)
        evaluation_rows = [{
            'question_id': question.id,
            'criterion_id': self.criterion.id,
            'score': 80,
            'max_score': 100,
            'explanation': 'The answer explains the implementation behavior.',
            'evidence': [{'source_type': 'CODE', 'file_path': 'src/calculate.py', 'start_line': 1, 'end_line': 2, 'claim': 'The function multiplies its input.'}],
            'strengths': ['Connects the code to its result.'],
            'missing_points': [],
            'recommendations': ['Discuss boundary cases.'],
        } for question in questions]
        evaluator = Mock()
        evaluator.generate.return_value = json.dumps({'evaluations': evaluation_rows})
        def context_for_source(_submission, _query, *, source_type, limit):
            return [self.code_chunk] if source_type == 'CODE' else [self.pdf_chunk]
        with (
            patch('apps.assessments.services.evaluation.retrieve_chunks', side_effect=context_for_source),
            patch('apps.assessments.services.evaluation.get_llm_provider', return_value=evaluator),
        ):
            evaluate_answer_submission(answer_submission.id)
        answer_submission.refresh_from_db()
        self.assertEqual(answer_submission.status, AnswerSubmission.Status.EVALUATED)

        self.client.force_authenticate(self.ta)
        self.assertEqual(self.client.get(f'/api/assessment-runs/{run.id}/evaluation/').status_code, 200)
        self.assertEqual(self.client.post(f'/api/assessment-runs/{run.id}/review/', {'status': 'IN_REVIEW'}, format='json').status_code, 200)
        self.assertEqual(self.client.post(
            f'/api/assessment-runs/{run.id}/criteria/{self.criterion.id}/override/',
            {'score': 90, 'reason': 'Verified against the submitted source and explanation.'}, format='json',
        ).status_code, 200)
        self.assertEqual(self.client.post(f'/api/assessment-runs/{run.id}/review/', {'status': 'REVIEWED'}, format='json').status_code, 200)

        self.client.force_authenticate(self.faculty)
        prepared = self.client.post('/api/reports/prepare/', {'assessment_run_id': run.id}, format='json')
        self.assertEqual(prepared.status_code, 201, prepared.data)
        report_id = prepared.data[0]['id']
        self.assertEqual(self.client.post(f'/api/reports/{report_id}/publish/').status_code, 200)

        self.client.force_authenticate(self.trainee)
        published = self.client.get('/api/reports/')
        self.assertEqual(published.status_code, 200)
        self.assertEqual(published.data['count'], 1)
        self.assertEqual(published.data['results'][0]['snapshot']['criteria'][0]['score'], '90.00')
