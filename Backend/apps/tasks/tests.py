from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.batches.models import Batch
from apps.rubrics.models import CompetencyLevel, Criterion, Rubric

from .models import Task


class TaskAPITests(APITestCase):
    def setUp(self):
        self.faculty = User.objects.create_user(
            username='faculty', password='password123', role=User.Role.FACULTY,
        )
        self.other_faculty = User.objects.create_user(
            username='other-faculty', password='password123', role=User.Role.FACULTY,
        )
        self.ta = User.objects.create_user(
            username='ta', password='password123', role=User.Role.TA,
        )
        self.trainee = User.objects.create_user(
            username='trainee', password='password123', role=User.Role.TRAINEE,
        )
        self.batch = Batch.objects.create(name='Faculty batch', faculty=self.faculty)
        self.batch.tas.add(self.ta)
        self.batch.trainees.add(self.trainee)
        self.other_batch = Batch.objects.create(name='Other batch', faculty=self.other_faculty)

        self.rubric = Rubric.objects.create(
            name='Backend Evaluation',
            description='Evaluate backend skills',
            created_by=self.faculty,
            is_active=True,
        )
        criterion = Criterion.objects.create(
            rubric=self.rubric,
            name='Implementation',
            description='Implementation quality',
            weight='100.00',
            max_score=5,
        )
        CompetencyLevel.objects.bulk_create([
            CompetencyLevel(criterion=criterion, level=level, description=f'{level} description')
            for level in ('L1', 'L2', 'L3', 'L4')
        ])

    def task_payload(self, **overrides):
        payload = {
            'title': 'Project Task',
            'description': 'Build a backend feature',
            'skill': 'Backend Development',
            'rubric': self.rubric.id,
            'batches': [self.batch.id],
            'questions_count': 6,
            'require_pdf': True,
            'allow_resubmission': False,
        }
        payload.update(overrides)
        return payload

    def create_task(self, **overrides):
        return self.client.post('/api/tasks/', self.task_payload(**overrides), format='json')

    def test_faculty_task_crud_and_response_shape(self):
        self.client.force_authenticate(self.faculty)
        created = self.create_task()
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data['status'], Task.Status.DRAFT)
        self.assertEqual(created.data['skill'], 'Backend Development')
        self.assertEqual(created.data['questions_count'], 6)
        self.assertTrue(created.data['require_pdf'])
        self.assertEqual(created.data['rubric']['name'], self.rubric.name)
        self.assertEqual(created.data['batches'], [{'id': self.batch.id, 'name': self.batch.name}])

        listed = self.client.get('/api/tasks/')
        self.assertEqual([item['id'] for item in listed.data['results']], [created.data['id']])

        updated = self.client.patch(
            f"/api/tasks/{created.data['id']}/",
            {'title': 'Updated Task', 'questions_count': 8},
            format='json',
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data['title'], 'Updated Task')
        self.assertEqual(updated.data['questions_count'], 8)

        deleted = self.client.delete(f"/api/tasks/{created.data['id']}/")
        self.assertEqual(deleted.status_code, 204)

    def test_faculty_can_assign_only_own_batches_and_owned_rubrics(self):
        self.client.force_authenticate(self.faculty)
        response = self.create_task(batches=[self.batch.id, self.other_batch.id])
        self.assertEqual(response.status_code, 400)

        foreign_rubric = Rubric.objects.create(
            name='Foreign rubric', created_by=self.other_faculty,
        )
        response = self.create_task(rubric=foreign_rubric.id)
        self.assertEqual(response.status_code, 400)

    def test_activation_completion_and_assignee_task_lists(self):
        self.client.force_authenticate(self.faculty)
        created = self.create_task()
        task_id = created.data['id']

        activated = self.client.post(f'/api/tasks/{task_id}/activate/', {}, format='json')
        self.assertEqual(activated.status_code, 200)
        self.assertEqual(activated.data['status'], Task.Status.ACTIVE)

        self.client.force_authenticate(self.trainee)
        trainee_tasks = self.client.get('/api/tasks/assigned-to-trainee/')
        self.assertEqual([task['id'] for task in trainee_tasks.data['results']], [task_id])

        self.client.force_authenticate(self.ta)
        ta_tasks = self.client.get('/api/tasks/assigned-to-ta/')
        self.assertEqual([task['id'] for task in ta_tasks.data['results']], [task_id])

        self.client.force_authenticate(self.faculty)
        completed = self.client.post(f'/api/tasks/{task_id}/complete/', {}, format='json')
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.data['status'], Task.Status.COMPLETED)

        self.client.force_authenticate(self.trainee)
        trainee_tasks = self.client.get('/api/tasks/')
        self.assertEqual(trainee_tasks.data['results'], [])

    def test_activation_requires_active_rubric_and_batch_assignment(self):
        self.client.force_authenticate(self.faculty)
        draft_rubric = Rubric.objects.create(name='Draft rubric', created_by=self.faculty)
        response = self.create_task(rubric=draft_rubric.id)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            self.client.post(f"/api/tasks/{response.data['id']}/activate/", {}, format='json').status_code,
            400,
        )

        unassigned = self.create_task(batches=[])
        self.assertEqual(unassigned.status_code, 400)

    def test_ta_and_trainee_cannot_create_or_modify_tasks(self):
        task = Task.objects.create(
            title='Existing', description='Existing task', skill='Backend',
            created_by=self.faculty, rubric=self.rubric, status=Task.Status.ACTIVE,
        )
        task.batches.add(self.batch)
        payload = self.task_payload()

        self.client.force_authenticate(self.ta)
        self.assertEqual(self.client.post('/api/tasks/', payload, format='json').status_code, 403)
        self.assertEqual(self.client.patch(f'/api/tasks/{task.id}/', {'title': 'No'}, format='json').status_code, 403)

        self.client.force_authenticate(self.trainee)
        self.assertEqual(self.client.post('/api/tasks/', payload, format='json').status_code, 403)
        self.assertEqual(self.client.patch(f'/api/tasks/{task.id}/', {'title': 'No'}, format='json').status_code, 403)

    def test_trainee_and_ta_lists_are_limited_to_assigned_batches(self):
        own_task = Task.objects.create(
            title='Own task', description='For own cohort', skill='Backend',
            created_by=self.faculty, rubric=self.rubric, status=Task.Status.ACTIVE,
        )
        own_task.batches.add(self.batch)
        other_task = Task.objects.create(
            title='Other task', description='For other cohort', skill='Backend',
            created_by=self.other_faculty, status=Task.Status.ACTIVE,
        )
        other_task.batches.add(self.other_batch)

        self.client.force_authenticate(self.trainee)
        response = self.client.get('/api/tasks/assigned-to-trainee/')
        self.assertEqual([item['id'] for item in response.data['results']], [own_task.id])

        self.client.force_authenticate(self.ta)
        response = self.client.get('/api/tasks/assigned-to-ta/')
        self.assertEqual([item['id'] for item in response.data['results']], [own_task.id])

