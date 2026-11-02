from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.batches.models import Batch


class BatchAPITests(APITestCase):
    def setUp(self):
        self.faculty = User.objects.create_user(
            username='meera',
            password='password123',
            role=User.Role.FACULTY,
        )
        self.other_faculty = User.objects.create_user(
            username='alex',
            password='password123',
            role=User.Role.FACULTY,
        )
        self.ta = User.objects.create_user(
            username='priya',
            password='password123',
            role=User.Role.TA,
            employee_id='T001',
        )
        self.trainee = User.objects.create_user(
            username='kunal',
            password='password123',
            role=User.Role.TRAINEE,
            employee_id='2345748',
        )

    def test_faculty_creates_and_lists_own_batches(self):
        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            '/api/batches/',
            {
                'name': 'DRF Batch 12',
                'description': 'DRF APIs',
                'start_date': '2026-09-01',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['faculty']['username'], 'meera')
        self.assertEqual(response.data['trainee_count'], 0)
        self.assertTrue(AuditEvent.objects.filter(action='batch-created').exists())

        Batch.objects.create(name='Hidden', faculty=self.other_faculty)
        listing = self.client.get('/api/batches/')
        names = [item['name'] for item in listing.data['results']]
        self.assertEqual(names, ['DRF Batch 12'])

        updated = self.client.patch(
            f"/api/batches/{response.data['id']}/",
            {'description': 'Updated description'},
            format='json',
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data['description'], 'Updated description')
        self.assertTrue(AuditEvent.objects.filter(action='batch-updated').exists())

        deleted = self.client.delete(f"/api/batches/{response.data['id']}/")
        self.assertEqual(deleted.status_code, 204)

    def test_ta_and_trainee_cannot_create_batch(self):
        self.client.force_authenticate(self.ta)
        response = self.client.post(
            '/api/batches/',
            {'name': 'Nope'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(self.trainee)
        response = self.client.post(
            '/api/batches/',
            {'name': 'Nope'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_membership_and_visibility(self):
        self.client.force_authenticate(self.faculty)
        batch = Batch.objects.create(name='DRF Batch 12', faculty=self.faculty)

        add_ta = self.client.post(
            f'/api/batches/{batch.id}/tas/',
            {'user_ids': [self.ta.id]},
            format='json',
        )
        self.assertEqual(add_ta.status_code, 200)
        self.assertEqual(add_ta.data['results'][0]['username'], 'priya')
        self.assertTrue(AuditEvent.objects.filter(action='tas-added').exists())

        add_trainee = self.client.post(
            f'/api/batches/{batch.id}/trainees/',
            {'user_ids': [self.trainee.id]},
            format='json',
        )
        self.assertEqual(add_trainee.status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(action='trainees-added').exists())

        search = self.client.get(
            f'/api/batches/{batch.id}/trainees/',
            {'search': '2345748'},
        )
        self.assertEqual(search.status_code, 200)
        self.assertEqual(len(search.data['results']), 1)

        self.client.force_authenticate(self.ta)
        listing = self.client.get('/api/batches/')
        self.assertEqual(len(listing.data['results']), 1)
        patch = self.client.patch(
            f'/api/batches/{batch.id}/',
            {'description': 'hack'},
            format='json',
        )
        self.assertEqual(patch.status_code, 403)

        self.client.force_authenticate(self.trainee)
        listing = self.client.get('/api/batches/')
        self.assertEqual(listing.data['results'][0]['name'], 'DRF Batch 12')

        outsider = User.objects.create_user(
            username='outsider',
            password='password123',
            role=User.Role.TRAINEE,
        )
        self.client.force_authenticate(outsider)
        listing = self.client.get('/api/batches/')
        self.assertEqual(listing.data['results'], [])
        detail = self.client.get(f'/api/batches/{batch.id}/')
        self.assertEqual(detail.status_code, 404)

    def test_remove_members(self):
        self.client.force_authenticate(self.faculty)
        batch = Batch.objects.create(name='DRF Batch 12', faculty=self.faculty)
        batch.trainees.add(self.trainee)
        response = self.client.delete(
            f'/api/batches/{batch.id}/trainees/',
            {'user_ids': [self.trainee.id]},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'], [])
        self.assertTrue(AuditEvent.objects.filter(action='trainees-removed').exists())

    def test_invalid_role_assignment_is_rejected(self):
        batch = Batch.objects.create(name='DRF Batch 12', faculty=self.faculty)
        self.client.force_authenticate(self.faculty)

        wrong_role = self.client.post(
            f'/api/batches/{batch.id}/tas/',
            {'user_ids': [self.trainee.id]},
            format='json',
        )
        self.assertEqual(wrong_role.status_code, 400)

        wrong_role = self.client.post(
            f'/api/batches/{batch.id}/trainees/',
            {'user_ids': [self.ta.id]},
            format='json',
        )
        self.assertEqual(wrong_role.status_code, 400)

    def test_assigned_ta_can_read_roster_but_trainee_cannot(self):
        batch = Batch.objects.create(name='DRF Batch 12', faculty=self.faculty)
        batch.tas.add(self.ta)
        batch.trainees.add(self.trainee)

        self.client.force_authenticate(self.ta)
        response = self.client.get(f'/api/batches/{batch.id}/trainees/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['id'], self.trainee.id)
        other_batch = Batch.objects.create(name='Other batch', faculty=self.faculty)
        self.assertEqual(self.client.get(f'/api/batches/{other_batch.id}/trainees/').status_code, 404)

        self.client.force_authenticate(self.trainee)
        response = self.client.get(f'/api/batches/{batch.id}/trainees/')
        self.assertEqual(response.status_code, 403)

    def test_cross_batch_access_is_denied(self):
        batch = Batch.objects.create(name='Private batch', faculty=self.faculty)
        other_batch = Batch.objects.create(name='Other batch', faculty=self.other_faculty)
        other_batch.trainees.add(self.trainee)

        self.client.force_authenticate(self.faculty)
        response = self.client.get(f'/api/batches/{other_batch.id}/')
        self.assertEqual(response.status_code, 404)

        self.client.force_authenticate(self.ta)
        response = self.client.get(f'/api/batches/{other_batch.id}/')
        self.assertEqual(response.status_code, 404)

        self.client.force_authenticate(self.trainee)
        response = self.client.get(f'/api/batches/{batch.id}/')
        self.assertEqual(response.status_code, 404)
