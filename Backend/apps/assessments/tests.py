import json
from unittest.mock import Mock, patch

from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.batches.models import Batch
from apps.rubrics.models import Criterion, Rubric
from apps.submissions.models import Submission
from apps.tasks.models import Task

from .models import AssessmentRun, GeneratedQuestion
from .services.llm import OpenAICompatibleLLM
from .services.question_generation import generate_questions


def valid_llm_response(criterion_id, code_path='src/scoring.py'):
    types = ['IMPLEMENTATION', 'IMPLEMENTATION', 'DESIGN', 'DECISION', 'DEBUGGING', 'DESIGN']
    questions = []
    for index, question_type in enumerate(types, start=1):
        questions.append({
            'question_text': f'How does the project handle scoring case {index}, and why is this approach appropriate?',
            'question_type': question_type,
            'competency_criterion_id': criterion_id,
            'difficulty': ['EASY', 'MEDIUM', 'HARD'][index % 3],
            'code_file': code_path,
            'code_line': 4,
            'code_snippet': 'return sum(scores)',
            'expected_answer_points': [f'Expected technical point {index}.'],
        })
    return json.dumps({'questions': questions})


class AssessmentPhaseFiveTests(APITestCase):
    def setUp(self):
        self.faculty = User.objects.create(username='phase5-faculty', role=User.Role.FACULTY)
        self.ta = User.objects.create(username='phase5-ta', role=User.Role.TA)
        self.trainee = User.objects.create(username='phase5-trainee', role=User.Role.TRAINEE)
        self.other_trainee = User.objects.create(username='phase5-other-trainee', role=User.Role.TRAINEE)
        self.batch = Batch.objects.create(name='Phase 5 batch', faculty=self.faculty)
        self.batch.trainees.add(self.trainee)
        self.batch.tas.add(self.ta)
        self.rubric = Rubric.objects.create(name='Backend competency', created_by=self.faculty)
        self.criterion = Criterion.objects.create(
            rubric=self.rubric,
            name='Implementation quality',
            description='Correctness, clarity, and maintainability.',
            weight='100.00',
            max_score=100,
        )
        self.task = Task.objects.create(
            title='Scoring API',
            description='Build an API that aggregates a set of assessment scores.',
            skill='Backend development',
            created_by=self.faculty,
            rubric=self.rubric,
            questions_count=6,
        )
        self.task.batches.add(self.batch)
        self.submission = Submission.objects.create(
            trainee=self.trainee,
            task=self.task,
            repository_url='https://code.example.org/team/scoring-api',
            status=Submission.Status.QUESTIONS_READY,
            indexed_commit_hash='a' * 40,
        )
        self.run = AssessmentRun.objects.create(
            submission=self.submission,
            status=AssessmentRun.Status.PROCESSING,
        )
        self.code_chunk = {
            'content': 'def total(scores):\n    # aggregate scores\n    if not scores:\n        return sum(scores)\n',
            'metadata': {
                'source_type': 'CODE',
                'file_path': 'src/scoring.py',
                'file_extension': '.py',
                'start_line': 1,
                'end_line': 5,
            },
        }
        self.pdf_chunk = {
            'content': 'The project explains why scores are aggregated before reporting.',
            'metadata': {'source_type': 'PDF', 'file_path': 'submissions/pdfs/explanation.pdf', 'page': 1},
        }

    def run_generation(self, llm_response=None):
        provider = Mock()
        provider.generate.return_value = llm_response or valid_llm_response(self.criterion.id)
        with (
            patch('apps.assessments.services.question_generation.retrieve_chunks', side_effect=[[self.code_chunk], [self.pdf_chunk]]),
            patch('apps.assessments.services.question_generation.get_llm_provider', return_value=provider),
        ):
            generate_questions(self.run.id)
        self.run.refresh_from_db()
        return provider

    def test_generation_persists_exactly_six_questions_using_rag(self):
        provider = self.run_generation()
        self.assertEqual(self.run.status, AssessmentRun.Status.COMPLETED)
        self.assertEqual(self.run.opencode_review_status, AssessmentRun.ReviewStatus.NOT_RUN)
        self.assertEqual(GeneratedQuestion.objects.filter(assessment_run=self.run).count(), 6)
        self.assertEqual(provider.generate.call_count, 1)
        first = GeneratedQuestion.objects.get(assessment_run=self.run, display_order=1)
        self.assertEqual(first.code_file, 'src/scoring.py')
        self.assertEqual(first.code_line, 4)
        self.assertEqual(first.competency_criterion, self.criterion)
        self.assertTrue(first.expected_answer_points)
        self.assertEqual(self.submission.__class__.objects.get(pk=self.submission.pk).status, Submission.Status.QUESTIONS_READY)

    def test_question_generation_does_not_require_opencode_review(self):
        provider = self.run_generation()
        self.assertEqual(self.run.status, AssessmentRun.Status.COMPLETED)
        self.assertEqual(self.run.opencode_review_status, AssessmentRun.ReviewStatus.NOT_RUN)
        self.assertEqual(provider.generate.call_count, 1)
        self.assertEqual(GeneratedQuestion.objects.filter(assessment_run=self.run).count(), 6)

    def test_missing_context_and_invalid_question_output_fail_without_partial_questions(self):
        with (
            patch('apps.assessments.services.question_generation.retrieve_chunks', return_value=[]),
            patch('apps.assessments.services.question_generation.get_llm_provider') as get_llm,
        ):
            generate_questions(self.run.id)
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, AssessmentRun.Status.FAILED)
        get_llm.assert_not_called()
        self.assertEqual(GeneratedQuestion.objects.filter(assessment_run=self.run).count(), 0)

        self.run.status = AssessmentRun.Status.PROCESSING
        self.run.save(update_fields=['status'])
        with (
            patch('apps.assessments.services.question_generation.retrieve_chunks', side_effect=[[self.code_chunk], [self.pdf_chunk]]),
            patch('apps.assessments.services.question_generation.get_llm_provider') as get_llm,
        ):
            get_llm.return_value.generate.return_value = '{not-json'
            generate_questions(self.run.id)
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, AssessmentRun.Status.FAILED)
        self.assertEqual(GeneratedQuestion.objects.filter(assessment_run=self.run).count(), 0)

    @patch('apps.assessments.services.llm.urlopen')
    @override_settings(
        LLM_PROVIDER='http',
        LLM_API_URL='https://llm.example/v1/chat/completions',
        LLM_API_KEY='test-only-key',
        LLM_MODEL='assessment-model',
    )
    def test_openai_compatible_provider_sends_low_temperature_and_parses_content(self, send):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({
            'choices': [{'message': {'content': '{"questions": []}'}}],
        }).encode()
        send.return_value = response

        content = OpenAICompatibleLLM().generate('system', 'user')
        request = send.call_args.args[0]
        self.assertEqual(content, '{"questions": []}')
        self.assertEqual(json.loads(request.data)['temperature'], 0.2)
        self.assertEqual(json.loads(request.data)['model'], 'assessment-model')
        self.assertIn('Authorization', request.headers)

    def test_faculty_can_start_generation_and_duplicate_requests_are_idempotent(self):
        self.run.status = AssessmentRun.Status.PENDING
        self.run.save(update_fields=['status'])
        self.client.force_authenticate(self.faculty)
        with patch('apps.assessments.services.question_generation.queue_question_generation', return_value=True) as queue:
            first = self.client.post(f'/api/submissions/{self.submission.id}/generate-questions/')
            second = self.client.post(f'/api/submissions/{self.submission.id}/generate-questions/')
        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 202)
        self.assertEqual(queue.call_count, 1, f'first={first.data}, second={second.data}')
        self.assertEqual(AssessmentRun.objects.filter(submission=self.submission).count(), 1)
        self.assertEqual(AssessmentRun.objects.get(submission=self.submission).status, AssessmentRun.Status.PROCESSING)

    def test_questions_are_scoped_and_expected_points_are_hidden_from_trainees(self):
        self.run.status = AssessmentRun.Status.COMPLETED
        self.run.save(update_fields=['status'])
        question = GeneratedQuestion.objects.create(
            submission=self.submission,
            assessment_run=self.run,
            question_text='Explain why this scoring implementation handles empty input this way.',
            competency_criterion=self.criterion,
            difficulty=GeneratedQuestion.Difficulty.MEDIUM,
            code_file='src/scoring.py',
            code_line=4,
            code_snippet='return sum(scores)',
            expected_answer_points=['Explain the chosen empty-input behavior.'],
            display_order=1,
        )
        self.client.force_authenticate(self.trainee)
        own = self.client.get(f'/api/questions/{question.id}/')
        self.assertEqual(own.status_code, 200)
        self.assertNotIn('expected_answer_points', own.data)
        self.assertEqual(own.data['competency_criterion']['name'], self.criterion.name)

        self.client.force_authenticate(self.other_trainee)
        self.assertEqual(self.client.get(f'/api/questions/{question.id}/').status_code, 404)
        self.assertEqual(
            self.client.get('/api/questions/', {'submission_id': self.submission.id}).data['count'],
            0,
        )

        self.client.force_authenticate(self.ta)
        staff_detail = self.client.get(f'/api/questions/{question.id}/')
        self.assertEqual(staff_detail.status_code, 200)
        self.assertIn('expected_answer_points', staff_detail.data)

