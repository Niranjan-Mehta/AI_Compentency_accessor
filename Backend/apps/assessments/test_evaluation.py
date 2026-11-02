import json
from unittest.mock import Mock, patch

from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.batches.models import Batch
from apps.rubrics.models import CompetencyLevel, Criterion, Rubric
from apps.submissions.models import Submission
from apps.tasks.models import Task

from .models import (
    AnswerSubmission,
    AssessmentRun,
    CriterionAssessment,
    GeneratedQuestion,
    QuestionEvaluation,
    TraineeAnswer,
)
from .services.evaluation import evaluate_answer_submission, level_for_score


class AnswerEvaluationWorkflowTests(APITestCase):
    def setUp(self):
        self.faculty = User.objects.create(username='evaluation-faculty', role=User.Role.FACULTY)
        self.ta = User.objects.create(username='evaluation-ta', role=User.Role.TA)
        self.outside_ta = User.objects.create(username='evaluation-outside-ta', role=User.Role.TA)
        self.trainee = User.objects.create(username='evaluation-trainee', role=User.Role.TRAINEE)
        self.other_trainee = User.objects.create(username='evaluation-other-trainee', role=User.Role.TRAINEE)
        self.batch = Batch.objects.create(name='Evaluation batch', faculty=self.faculty)
        self.batch.trainees.add(self.trainee)
        self.batch.tas.add(self.ta)
        self.rubric = Rubric.objects.create(name='Evaluation rubric', created_by=self.faculty)
        self.criteria = []
        for index, (name, weight) in enumerate((('Implementation', '70.00'), ('Design', '30.00')), start=1):
            criterion = Criterion.objects.create(
                rubric=self.rubric,
                name=name,
                description=f'{name} quality in the submitted project.',
                weight=weight,
                max_score=100,
            )
            CompetencyLevel.objects.bulk_create([
                CompetencyLevel(criterion=criterion, level=level, description=f'{level} for {name}')
                for level in ('L1', 'L2', 'L3', 'L4')
            ])
            self.criteria.append(criterion)
        self.task = Task.objects.create(
            title='Evaluate service implementation',
            description='Explain the service behavior, design, and tradeoffs.',
            skill='Backend development',
            created_by=self.faculty,
            rubric=self.rubric,
            allow_resubmission=False,
        )
        self.task.batches.add(self.batch)
        self.submission = Submission.objects.create(
            trainee=self.trainee,
            task=self.task,
            repository_url='https://code.example.org/team/evaluation',
            status=Submission.Status.QUESTIONS_READY,
            indexed_commit_hash='b' * 40,
        )
        self.run = AssessmentRun.objects.create(
            submission=self.submission,
            status=AssessmentRun.Status.COMPLETED,
        )
        self.questions = []
        for index in range(1, 7):
            criterion = self.criteria[0] if index <= 3 else self.criteria[1]
            self.questions.append(GeneratedQuestion.objects.create(
                submission=self.submission,
                assessment_run=self.run,
                question_text=f'Explain implementation decision {index} in your project and its tradeoffs.',
                competency_criterion=criterion,
                difficulty=GeneratedQuestion.Difficulty.MEDIUM,
                code_file='src/service.py',
                code_line=2,
                code_snippet='return result',
                expected_answer_points=[f'Internal expected point {index}.'],
                display_order=index,
            ))
        self.code_chunk = {
            'content': 'def process(value):\n    result = value * 2\n    return result\n',
            'metadata': {
                'source_type': 'CODE',
                'file_path': 'src/service.py',
                'file_extension': '.py',
                'start_line': 1,
                'end_line': 3,
            },
        }
        self.pdf_chunk = {
            'content': 'The project explanation describes the intended processing behavior.',
            'metadata': {
                'source_type': 'PDF',
                'file_path': 'explanation.pdf',
                'page': 1,
            },
        }

    def answer_url(self):
        return f'/api/assessment-runs/{self.run.id}/answers/'

    def evaluation_url(self):
        return f'/api/assessment-runs/{self.run.id}/evaluation/'

    def save_all_answers(self):
        self.client.force_authenticate(self.trainee)
        for question in self.questions:
            response = self.client.post(self.answer_url(), {
                'question_id': question.id,
                'answer_text': f'My explanation for implementation decision {question.display_order}.',
            }, format='json')
            self.assertEqual(response.status_code, 200, response.data)
        return AnswerSubmission.objects.get(assessment_run=self.run)

    def valid_evaluation_response(self):
        rows = []
        for question in self.questions:
            criterion = question.competency_criterion
            score = 80 if criterion == self.criteria[0] else 50
            rows.append({
                'question_id': question.id,
                'criterion_id': criterion.id,
                'score': score,
                'max_score': criterion.max_score,
                'explanation': 'The answer explains the selected implementation using evidence from the submission.',
                'evidence': [
                    {
                        'source_type': 'CODE',
                        'file_path': 'src/service.py',
                        'start_line': 2,
                        'end_line': 3,
                        'page': None,
                        'claim': 'The cited implementation supports the explanation of processing behavior.',
                    },
                    {
                        'source_type': 'PDF',
                        'file_path': 'explanation.pdf',
                        'start_line': None,
                        'end_line': None,
                        'page': 1,
                        'claim': 'The explanation document describes the intended processing behavior.',
                    },
                ],
                'strengths': ['Connects the answer to the project behavior.'],
                'missing_points': ['Could explain one edge case in more detail.'],
                'recommendations': ['Discuss how the service handles invalid input.'],
            })
        return json.dumps({'evaluations': rows})

    def run_evaluation(self, response_text=None, *, provider_error=None):
        answer_submission = AnswerSubmission.objects.get(assessment_run=self.run)
        answer_submission.status = AnswerSubmission.Status.SUBMITTED
        answer_submission.save(update_fields=['status'])
        provider = Mock()
        if provider_error:
            provider.generate.side_effect = provider_error
        else:
            provider.generate.return_value = response_text or self.valid_evaluation_response()

        def retrieve(_submission, _query, *, source_type, limit):
            self.assertEqual(_submission.id, self.submission.id)
            self.assertEqual(limit, 3)
            return [self.code_chunk if source_type == 'CODE' else self.pdf_chunk]

        with (
            patch('apps.assessments.services.evaluation.retrieve_chunks', side_effect=retrieve),
            patch('apps.assessments.services.evaluation.get_llm_provider', return_value=provider),
        ):
            evaluate_answer_submission(answer_submission.id)
        answer_submission.refresh_from_db()
        return answer_submission, provider

    def test_draft_answers_are_saved_updated_and_return_questions_without_hidden_points(self):
        self.client.force_authenticate(self.trainee)
        initial = self.client.get(self.answer_url())
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(len(initial.data['questions']), 6)
        question = self.questions[0]
        first = self.client.post(self.answer_url(), {
            'question_id': question.id,
            'answer_text': 'Initial explanation of my implementation decision.',
        }, format='json')
        updated = self.client.put(
            f'/api/assessment-runs/{self.run.id}/answers/{question.id}/',
            {'answer_text': 'Updated explanation of my implementation decision.'},
            format='json',
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(TraineeAnswer.objects.count(), 1)
        self.assertEqual(TraineeAnswer.objects.get().answer_text, 'Updated explanation of my implementation decision.')
        self.assertNotIn('expected_answer_points', str(initial.data) + str(updated.data))

    def test_submission_requires_every_answer_and_duplicate_evaluation_is_prevented(self):
        self.client.force_authenticate(self.trainee)
        missing = self.client.post(f'/api/assessment-runs/{self.run.id}/submit-answers/')
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(AnswerSubmission.objects.count(), 0)

        self.save_all_answers()
        submit_url = f'/api/assessment-runs/{self.run.id}/submit-answers/'
        with patch('apps.assessments.workflow_views.queue_evaluation', return_value=True) as queue:
            first = self.client.post(submit_url)
            duplicate = self.client.post(submit_url)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(duplicate.status_code, 202)
        self.assertEqual(queue.call_count, 1)
        answer_submission = AnswerSubmission.objects.get(assessment_run=self.run)
        self.assertEqual(answer_submission.status, AnswerSubmission.Status.SUBMITTED)
        locked = self.client.post(self.answer_url(), {
            'question_id': self.questions[0].id,
            'answer_text': 'An attempted late answer change.',
        }, format='json')
        self.assertEqual(locked.status_code, 400)

    def test_evaluation_scores_are_weighted_and_ta_override_recalculates_final_score(self):
        self.save_all_answers()
        answer_submission, provider = self.run_evaluation()
        self.assertEqual(answer_submission.status, AnswerSubmission.Status.EVALUATED)
        self.assertEqual(QuestionEvaluation.objects.count(), 6)
        self.assertEqual(provider.generate.call_count, 1)
        criteria = {item.criterion_id: item for item in answer_submission.criterion_assessments.all()}
        self.assertEqual(criteria[self.criteria[0].id].ai_score, 80)
        self.assertEqual(criteria[self.criteria[1].id].ai_score, 50)
        self.assertEqual(answer_submission.overall_ai_score, 71)
        self.assertEqual(answer_submission.overall_ai_level, 'L3')

        self.client.force_authenticate(self.ta)
        review = self.client.post(f'/api/assessment-runs/{self.run.id}/review/', {'status': 'IN_REVIEW'}, format='json')
        self.assertEqual(review.status_code, 200)
        missing_reason = self.client.post(
            f'/api/assessment-runs/{self.run.id}/criteria/{self.criteria[0].id}/override/',
            {'score': 20},
            format='json',
        )
        self.assertEqual(missing_reason.status_code, 400)
        override = self.client.post(
            f'/api/assessment-runs/{self.run.id}/criteria/{self.criteria[0].id}/override/',
            {'score': 20, 'reason': 'The response did not demonstrate the stated implementation behavior.'},
            format='json',
        )
        self.assertEqual(override.status_code, 200, override.data)
        answer_submission.refresh_from_db()
        overridden = answer_submission.criterion_assessments.get(criterion=self.criteria[0])
        self.assertEqual(overridden.ai_score, 80)
        self.assertEqual(overridden.final_score, 20)
        self.assertEqual(overridden.overridden_by, self.ta)
        self.assertEqual(answer_submission.overall_ai_score, 71)
        self.assertEqual(answer_submission.overall_final_score, 29)
        self.assertEqual(answer_submission.overall_final_level, 'L2')

        results = self.client.get(self.evaluation_url())
        self.assertEqual(results.status_code, 200)
        self.assertEqual(len(results.data['evaluations']), 6)
        self.assertNotIn('expected_answer_points', str(results.data))
        self.assertEqual(results.data['criteria'][0]['override_reason'], overridden.override_reason)
        self.client.force_authenticate(self.trainee)
        trainee_results = self.client.get(self.evaluation_url())
        self.assertEqual(trainee_results.status_code, 200)
        self.assertNotIn('override_reason', str(trainee_results.data))
        self.assertNotIn('expected_answer_points', str(trainee_results.data))
        self.client.force_authenticate(self.faculty)
        self.assertEqual(self.client.get(self.evaluation_url()).status_code, 200)

    def test_evaluation_rejects_invalid_json_without_partial_scores(self):
        self.save_all_answers()
        answer_submission, _ = self.run_evaluation('{invalid-json')
        self.assertEqual(answer_submission.status, AnswerSubmission.Status.FAILED)
        self.assertIn('invalid JSON', answer_submission.evaluation_error)
        self.assertEqual(QuestionEvaluation.objects.count(), 0)
        self.assertEqual(CriterionAssessment.objects.count(), 0)
        self.assertIsNone(answer_submission.overall_ai_score)

    def test_missing_llm_configuration_fails_clearly_and_can_be_retried(self):
        self.save_all_answers()
        answer_submission = AnswerSubmission.objects.get(assessment_run=self.run)
        answer_submission.status = AnswerSubmission.Status.SUBMITTED
        answer_submission.save(update_fields=['status'])
        with (
            override_settings(LLM_PROVIDER='http', LLM_API_URL='', LLM_MODEL=''),
            patch('apps.assessments.services.evaluation.retrieve_chunks', return_value=[self.code_chunk]),
        ):
            evaluate_answer_submission(answer_submission.id)
        answer_submission.refresh_from_db()
        self.assertEqual(answer_submission.status, AnswerSubmission.Status.FAILED)
        self.assertIn('LLM_API_URL', answer_submission.evaluation_error)
        self.client.force_authenticate(self.trainee)
        status_response = self.client.get(f'/api/assessment-runs/{self.run.id}/evaluation-status/')
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.data['error'], 'Evaluation failed. Please contact your TA.')

    def test_trainee_isolation_ta_assignment_and_faculty_batch_scope(self):
        self.save_all_answers()
        self.client.force_authenticate(self.other_trainee)
        self.assertEqual(self.client.get(self.answer_url()).status_code, 404)
        self.assertEqual(self.client.post(self.answer_url(), {
            'question_id': self.questions[0].id,
            'answer_text': 'Trying to answer another trainee assessment.',
        }, format='json').status_code, 404)

        self.client.force_authenticate(self.outside_ta)
        self.assertEqual(self.client.get(f'/api/assessment-runs/{self.run.id}/').status_code, 404)
        self.client.force_authenticate(self.faculty)
        self.assertEqual(self.client.get(f'/api/assessment-runs/{self.run.id}/').status_code, 200)
        self.assertEqual(self.client.post(f'/api/assessment-runs/{self.run.id}/review/', {
            'status': 'IN_REVIEW',
        }, format='json').status_code, 403)

    def test_competency_level_mapping_and_override_range(self):
        self.assertEqual(level_for_score(10, 100), 'L1')
        self.assertEqual(level_for_score(35, 100), 'L2')
        self.assertEqual(level_for_score(60, 100), 'L3')
        self.assertEqual(level_for_score(80, 100), 'L4')
        self.save_all_answers()
        answer_submission, _ = self.run_evaluation()
        self.client.force_authenticate(self.ta)
        self.client.post(f'/api/assessment-runs/{self.run.id}/review/', {'status': 'IN_REVIEW'}, format='json')
        invalid = self.client.post(
            f'/api/assessment-runs/{self.run.id}/criteria/{self.criteria[0].id}/override/',
            {'score': 101, 'reason': 'Out of range test.'},
            format='json',
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(answer_submission.criterion_assessments.filter(final_score__isnull=False).exists())

    def test_failed_provider_call_sets_failed_status_without_scores(self):
        self.save_all_answers()
        answer_submission, _ = self.run_evaluation(provider_error=RuntimeError('Evaluation provider request failed.'))
        self.assertEqual(answer_submission.status, AnswerSubmission.Status.FAILED)
        self.assertIn('provider request failed', answer_submission.evaluation_error)
        self.assertEqual(QuestionEvaluation.objects.count(), 0)

    def test_llm_timeout_and_invalid_scores_fail_without_partial_evaluation(self):
        self.save_all_answers()
        timed_out, _ = self.run_evaluation(provider_error=TimeoutError('provider timed out'))
        self.assertEqual(timed_out.status, AnswerSubmission.Status.FAILED)
        self.assertIn('timed out', timed_out.evaluation_error)

        payload = json.loads(self.valid_evaluation_response())
        payload['evaluations'][0]['score'] = 101
        invalid, _ = self.run_evaluation(json.dumps(payload))
        self.assertEqual(invalid.status, AnswerSubmission.Status.FAILED)
        self.assertIn('outside the valid range', invalid.evaluation_error)
        self.assertEqual(QuestionEvaluation.objects.count(), 0)
        self.assertEqual(CriterionAssessment.objects.count(), 0)

    def test_ta_cannot_publish_and_task_resubmission_setting_controls_edits(self):
        self.save_all_answers()
        answer_submission, _ = self.run_evaluation()
        self.client.force_authenticate(self.ta)
        self.assertIn(self.client.post(f'/api/assessment-runs/{self.run.id}/publish/').status_code, (404, 405))
        self.client.force_authenticate(self.trainee)
        self.task.allow_resubmission = True
        self.task.save(update_fields=['allow_resubmission'])
        response = self.client.post(self.answer_url(), {
            'question_id': self.questions[0].id,
            'answer_text': 'Updated answer after the task enabled another attempt.',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        answer_submission.refresh_from_db()
        self.assertEqual(answer_submission.status, AnswerSubmission.Status.DRAFT)
        self.assertEqual(answer_submission.criterion_assessments.count(), 0)
