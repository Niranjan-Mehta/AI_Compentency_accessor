from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import User
from apps.batches.models import Batch
from apps.rubrics.models import CompetencyLevel, Criterion, Rubric
from apps.tasks.models import Task
from apps.submissions.models import Submission
from apps.assessments.models import (AnswerSubmission, AssessmentRun, CriterionAssessment,
                                     GeneratedQuestion, QuestionEvaluation, TraineeAnswer)
from apps.assessments.services.evaluation import level_for_score, recalculate_totals
from apps.reports.models import Report


DEMO_PASSWORD = 'LocalDemo-2026!'
LEVEL_TEXT = {
    'L1': 'Needs step-by-step guidance and has difficulty explaining the concept.',
    'L2': 'Applies the concept with guidance and explains the main decisions.',
    'L3': 'Applies the concept independently and explains trade-offs clearly.',
    'L4': 'Applies the concept confidently, handles edge cases, and justifies alternatives.',
}


class Command(BaseCommand):
    help = 'Create idempotent local demonstration users, batches, rubrics, tasks and sample submissions.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Demo seeding is disabled unless DEBUG=True.')

        faculty = self.user('faculty', 'Meera', 'Iyer', User.Role.FACULTY)
        tas = [self.user(f'ta{i}', first, last, User.Role.TA) for i, (first, last) in enumerate(
            [('Priya', 'Shah'), ('Karthik', 'Menon'), ('Sana', 'Ali')], start=1
        )]
        trainees = []
        for batch_index, names in enumerate([
            [('Ravi', 'Kumar'), ('Anita', 'Rao'), ('Sameer', 'Joshi')],
            [('Kunal', 'Kumar'), ('Neha', 'Patel'), ('Arjun', 'Nair')],
            [('Maya', 'Singh'), ('Dev', 'Sharma'), ('Isha', 'Das')],
        ], start=1):
            trainees.append([self.user(f'trainee{batch_index}_{i}', first, last, User.Role.TRAINEE)
                             for i, (first, last) in enumerate(names, start=1)])

        batches = []
        for index in range(1, 4):
            batch, batch_created = Batch.objects.get_or_create(
                name=f'DRF Batch {11 + index}', faculty=faculty,
                defaults={'description': 'Django REST Framework APIs, authentication, data modeling and testing.',
                          'start_date': timezone.localdate() - timedelta(days=35),
                          'end_date': timezone.localdate() + timedelta(days=55)},
            )
            if batch_created:
                batch.trainees.add(*trainees[index - 1])
                batch.tas.add(tas[index - 1])
            batches.append(batch)

        rubric, created = Rubric.objects.get_or_create(
            name='DRF API Competency', created_by=faculty,
            defaults={'description': 'Evaluate API design, data modeling, security and testing.', 'is_active': True},
        )
        if created:
            criteria = [
                ('API Design', 'Endpoint structure, serializers and HTTP behavior.', 30),
                ('Database Design', 'Model relationships, constraints and query choices.', 25),
                ('Security', 'Authentication, authorization and input validation.', 25),
                ('Testing', 'Coverage of expected behavior and important edge cases.', 20),
            ]
            for name, description, weight in criteria:
                criterion = Criterion.objects.create(rubric=rubric, name=name, description=description,
                                                     weight=weight, max_score=100)
                CompetencyLevel.objects.bulk_create([
                    CompetencyLevel(criterion=criterion, level=level, description=text)
                    for level, text in LEVEL_TEXT.items()
                ])

        task_specs = [
            ('Ticket API with DRF', 'Build a ticket API with validated CRUD endpoints and clear permissions.', 'DRF API design'),
            ('JWT authentication and access control', 'Add role-aware authentication and test protected endpoints.', 'Authentication and security'),
            ('Pagination, filtering and tests', 'Add searchable list endpoints and focused automated tests.', 'Testing and API design'),
        ]
        tasks = []
        for title, description, skill in task_specs:
            task, task_created = Task.objects.get_or_create(
                title=title, created_by=faculty,
                defaults={'description': description, 'skill': skill, 'rubric': rubric,
                          'due_date': timezone.now() + timedelta(days=14), 'questions_count': 6,
                          'require_pdf': False, 'allow_resubmission': True, 'status': Task.Status.ACTIVE},
            )
            if task_created:
                task.batches.add(*batches)
            tasks.append(task)

        # A sample record exercises the real submission list without starting heavy processing.
        for sample_index, trainee in enumerate(trainees[0][:2]):
            submission, submission_created = Submission.objects.get_or_create(
                trainee=trainee, task=tasks[0],
                defaults={'repository_url': 'https://github.com/octocat/Hello-World',
                          'branch': 'master', 'status': Submission.Status.SUBMITTED},
            )
            if submission_created:
                self.seed_assessment(submission, rubric, batches[0], faculty, sample_index)

        self.stdout.write(self.style.SUCCESS(
            'Demo records are ready. Local demo password for newly created demo accounts: ' + DEMO_PASSWORD
        ))

    @staticmethod
    def user(slug, first, last, role):
        username = f'demo_{slug}'
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': f'{username}@example.test', 'first_name': first, 'last_name': last,
                      'role': role, 'employee_id': f'DEMO-{slug.upper()}'},
        )
        if created:
            user.is_active = True
            user.set_password(DEMO_PASSWORD)
            user.save()
        elif user.role != role:
            raise CommandError(f'Reserved demo username {username} already exists with a different role.')
        return user

    @staticmethod
    def seed_assessment(submission, rubric, batch, faculty, sample_index):
        run, created = AssessmentRun.objects.get_or_create(
            submission=submission,
            defaults={'status': AssessmentRun.Status.COMPLETED},
        )
        if not created:
            return
        criteria = list(rubric.criteria.order_by('id'))
        for order in range(1, submission.task.questions_count + 1):
            criterion = criteria[(order - 1) % len(criteria)]
            question, _ = GeneratedQuestion.objects.get_or_create(
                assessment_run=run, display_order=order,
                defaults={
                    'submission': submission,
                    'competency_criterion': criterion,
                    'difficulty': [GeneratedQuestion.Difficulty.EASY, GeneratedQuestion.Difficulty.MEDIUM,
                                  GeneratedQuestion.Difficulty.HARD][(order - 1) % 3],
                    'question_text': f'Explain how your project addresses {criterion.name.lower()} and describe one trade-off you considered.',
                    'code_file': None, 'code_line': None, 'code_snippet': '',
                    'expected_answer_points': [criterion.name, 'explanation', 'trade-off'],
                },
            )
        answers, _ = AnswerSubmission.objects.get_or_create(
            assessment_run=run,
            defaults={'status': AnswerSubmission.Status.EVALUATED,
                      'review_status': AnswerSubmission.ReviewStatus.REVIEWED},
        )
        for question in run.questions.select_related('competency_criterion').order_by('display_order'):
            answer, _ = TraineeAnswer.objects.get_or_create(
                answer_submission=answers, question=question,
                defaults={'answer_text': f'The implementation handles {question.competency_criterion.name.lower()} through explicit validation and role-scoped behavior. I chose this approach to keep the workflow predictable and testable.'},
            )
            QuestionEvaluation.objects.get_or_create(
                answer=answer,
                defaults={'criterion': question.competency_criterion, 'score': 72 + sample_index * 8,
                          'max_score': question.competency_criterion.max_score,
                          'explanation': 'The response identifies the implementation choice and explains its purpose.',
                          'evidence': [], 'strengths': ['Clear rationale'],
                          'missing_points': ['Could discuss an alternative in more detail.'],
                          'recommendations': ['Compare the trade-offs with an alternative.']},
            )
        for index, criterion in enumerate(criteria):
            score = 55 + ((index * 9 + sample_index * 12) % 40)
            level = level_for_score(score, criterion.max_score)
            CriterionAssessment.objects.get_or_create(
                answer_submission=answers, criterion=criterion,
                defaults={'ai_score': score, 'final_score': score, 'max_score': criterion.max_score,
                          'weight': criterion.weight, 'ai_level': level, 'final_level': level},
            )
        recalculate_totals(answers)
        answers.refresh_from_db()
        now_updated = answers.updated_at.isoformat()
        snapshot = {
            'task': {'id': submission.task_id, 'title': submission.task.title, 'skill': submission.task.skill},
            'trainee': {'id': submission.trainee_id, 'name': submission.trainee.get_full_name() or submission.trainee.username,
                        'employee_id': submission.trainee.employee_id},
            'batch': {'id': batch.id, 'name': batch.name}, 'assessment_run_id': run.id,
            'submission_id': submission.id, 'overall_score': str(answers.overall_final_score),
            'ai_overall_score': str(answers.overall_ai_score), 'competency_level': answers.overall_final_level,
            'ai_competency_level': answers.overall_ai_level,
            'criteria': [{'criterion_id': row.criterion_id, 'name': row.criterion.name,
                          'weight': str(row.weight), 'score': str(row.effective_score),
                          'ai_score': str(row.ai_score), 'max_score': row.max_score,
                          'level': row.effective_level, 'ai_level': row.ai_level,
                          'feedback': [], 'override_reason': '', 'overridden_by': None, 'overridden_at': None}
                         for row in answers.criterion_assessments.select_related('criterion').order_by('criterion_id')],
            'ta_review': {'status': 'REVIEWED', 'overrides': []},
            'source_updated_at': now_updated, 'prepared_at': timezone.now().isoformat(),
        }
        published = sample_index == 0
        report, _ = Report.objects.get_or_create(
            assessment_run=run, batch=batch,
            defaults={'trainee': submission.trainee, 'task': submission.task,
                      'overall_score': answers.overall_final_score,
                      'competency_level': answers.overall_final_level, 'snapshot': snapshot,
                      'status': Report.Status.PUBLISHED if published else Report.Status.DRAFT,
                      'published_at': timezone.now() if published else None,
                      'published_by': faculty if published else None},
        )
        submission.status = Submission.Status.PUBLISHED if published else Submission.Status.UNDER_REVIEW
        submission.save(update_fields=['status', 'updated_at'])
