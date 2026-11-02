from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.batches.models import Batch
from apps.tasks.models import Task

from .models import CompetencyLevel, Criterion, Rubric


def criterion(name='Implementation', weight='100.00', max_score=5):
    return {
        'name': name,
        'description': 'Implementation quality',
        'weight': weight,
        'max_score': max_score,
        'levels': [
            {'level': level, 'description': f'{level} description'}
            for level in ('L1', 'L2', 'L3', 'L4')
        ],
    }


class RubricAPITests(APITestCase):
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

    def payload(self):
        return {
            'name': 'Backend Evaluation',
            'description': 'Evaluate backend skills',
            'criteria': [criterion()],
        }

    def test_faculty_creates_lists_retrieves_and_updates_rubric(self):
        self.client.force_authenticate(self.faculty)
        created = self.client.post('/api/rubrics/', self.payload(), format='json')
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data['status'], 'DRAFT')
        self.assertEqual(len(created.data['criteria'][0]['levels']), 4)

        detail = self.client.get(f"/api/rubrics/{created.data['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['criteria'][0]['max_score'], 5)

        listed = self.client.get('/api/rubrics/')
        self.assertEqual(len(listed.data), 1)

        updated_payload = self.payload()
        updated_payload['criteria'][0]['name'] = 'API Design'
        updated = self.client.put(
            f"/api/rubrics/{created.data['id']}/",
            updated_payload,
            format='json',
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data['criteria'][0]['name'], 'API Design')

    def test_rubric_weight_score_and_level_validation(self):
        self.client.force_authenticate(self.faculty)

        bad_weights = self.payload()
        bad_weights['criteria'][0]['weight'] = '99.00'
        response = self.client.post('/api/rubrics/', bad_weights, format='json')
        self.assertEqual(response.status_code, 400)

        bad_score = self.payload()
        bad_score['criteria'][0]['max_score'] = 0
        response = self.client.post('/api/rubrics/', bad_score, format='json')
        self.assertEqual(response.status_code, 400)

        missing_level = self.payload()
        missing_level['criteria'][0]['levels'].pop()
        response = self.client.post('/api/rubrics/', missing_level, format='json')
        self.assertEqual(response.status_code, 400)

    def test_only_faculty_can_manage_rubrics_and_list_is_owner_scoped(self):
        rubric = Rubric.objects.create(name='Other', created_by=self.other_faculty)
        self.client.force_authenticate(self.ta)
        self.assertEqual(self.client.get('/api/rubrics/').status_code, 403)
        self.assertEqual(self.client.post('/api/rubrics/', self.payload(), format='json').status_code, 403)

        self.client.force_authenticate(self.faculty)
        self.assertEqual(self.client.get(f'/api/rubrics/{rubric.id}/').status_code, 404)

    def test_draft_can_be_activated_and_only_drafts_can_be_deleted(self):
        self.client.force_authenticate(self.faculty)
        created = self.client.post('/api/rubrics/', self.payload(), format='json')
        activate = self.client.post(f"/api/rubrics/{created.data['id']}/activate/", {}, format='json')
        self.assertEqual(activate.status_code, 200)
        self.assertEqual(activate.data['status'], 'ACTIVE')
        self.assertEqual(
            self.client.delete(f"/api/rubrics/{created.data['id']}/").status_code,
            400,
        )

        draft = Rubric.objects.create(name='Draft', created_by=self.faculty)
        self.assertEqual(self.client.delete(f'/api/rubrics/{draft.id}/').status_code, 204)

    def test_rubric_used_by_assigned_task_is_immutable(self):
        self.client.force_authenticate(self.faculty)
        response = self.client.post('/api/rubrics/', self.payload(), format='json')
        rubric = Rubric.objects.get(pk=response.data['id'])
        batch = Batch.objects.create(name='Backend cohort', faculty=self.faculty)
        task = Task.objects.create(
            title='Use rubric', description='Task', created_by=self.faculty, rubric=rubric,
        )
        task.batches.add(batch)

        changed = self.payload()
        changed['name'] = 'Changed'
        update = self.client.patch(f'/api/rubrics/{rubric.id}/', changed, format='json')
        self.assertEqual(update.status_code, 400)
        self.assertEqual(self.client.delete(f'/api/rubrics/{rubric.id}/').status_code, 400)
        self.assertEqual(Criterion.objects.get(rubric=rubric).name, 'Implementation')
        self.assertEqual(CompetencyLevel.objects.filter(criterion__rubric=rubric).count(), 4)
