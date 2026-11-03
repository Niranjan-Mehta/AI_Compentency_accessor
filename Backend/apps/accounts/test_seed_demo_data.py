from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.batches.models import Batch
from apps.rubrics.models import Rubric, Criterion, CompetencyLevel
from apps.tasks.models import Task
from apps.submissions.models import Submission
from apps.assessments.models import AssessmentRun, GeneratedQuestion, AnswerSubmission, TraineeAnswer, QuestionEvaluation
from apps.reports.models import Report


@override_settings(DEBUG=True)
class DemoSeedCommandTests(TestCase):
    def test_seed_is_idempotent_and_keeps_existing_records(self):
        preexisting = User.objects.create_user(username='manual_user', password='long-test-password', role=User.Role.TRAINEE)
        for _ in range(2):
            call_command('seed_demo_data', stdout=StringIO())
        models = (User, Batch, Rubric, Criterion, CompetencyLevel, Task, Submission, AssessmentRun,
                  GeneratedQuestion, AnswerSubmission, TraineeAnswer, QuestionEvaluation, Report)
        expected = {model: model.objects.count() for model in models}
        call_command('seed_demo_data', stdout=StringIO())
        self.assertEqual(expected, {model: model.objects.count() for model in expected})
        preexisting.refresh_from_db()
        self.assertTrue(preexisting.check_password('long-test-password'))
        self.assertTrue(User.objects.get(username='demo_faculty').check_password('LocalDemo-2026!'))
        self.assertEqual(Batch.objects.count(), 3)
