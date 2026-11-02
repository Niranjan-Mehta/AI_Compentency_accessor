from rest_framework.test import APITestCase
from django.core import mail
from django.test import override_settings

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.batches.models import Batch


class AuthAPITests(APITestCase):
    def setUp(self):
        self.faculty = User.objects.create_user(
            username='meera',
            email='meera@institution.edu',
            password='password123',
            role=User.Role.FACULTY,
            employee_id='F001',
        )
        self.ta = User.objects.create_user(
            username='priya',
            email='priya@institution.edu',
            password='password123',
            role=User.Role.TA,
            employee_id='T001',
        )

    def test_login_returns_role_and_employee_id(self):
        response = self.client.post(
            '/api/auth/login/',
            {'username': 'meera', 'password': 'password123'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['role'], User.Role.FACULTY)
        self.assertEqual(response.data['employee_id'], 'F001')
        self.assertEqual(response.data['username'], 'meera')

    def test_login_accepts_email_in_username_field(self):
        response = self.client.post(
            '/api/auth/login/',
            {'username': 'meera@institution.edu', 'password': 'password123'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['role'], User.Role.FACULTY)
        self.assertEqual(response.data['employee_id'], 'F001')

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(
            '/api/auth/login/',
            {'username': 'meera@institution.edu', 'password': 'incorrect-password'},
            format='json',
        )
        self.assertEqual(response.status_code, 401)

    def test_profile_includes_employee_id(self):
        self.client.force_authenticate(self.faculty)
        response = self.client.get('/api/auth/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['employee_id'], 'F001')
        self.assertEqual(response.data['role'], User.Role.FACULTY)

    def test_profile_update_cannot_change_role_or_employee_id(self):
        self.client.force_authenticate(self.ta)
        response = self.client.patch(
            '/api/auth/profile/',
            {'first_name': 'Priya', 'role': User.Role.FACULTY, 'employee_id': 'ADMIN'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['first_name'], 'Priya')
        self.assertEqual(response.data['role'], User.Role.TA)
        self.assertEqual(response.data['employee_id'], 'T001')

    def test_employee_id_must_be_unique(self):
        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            '/api/auth/create-user/',
            {
                'username': 'duplicate-id',
                'password': 'password123',
                'role': User.Role.TRAINEE,
                'employee_id': 'T001',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('employee_id', response.data)

    def test_faculty_cannot_create_faculty_account(self):
        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            '/api/auth/create-user/',
            {
                'username': 'new-faculty',
                'password': 'password123',
                'role': User.Role.FACULTY,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_create_user_faculty_only(self):
        self.client.force_authenticate(self.ta)
        response = self.client.post(
            '/api/auth/create-user/',
            {
                'username': 'kunal',
                'email': 'kunal@institution.edu',
                'password': 'password123',
                'role': User.Role.TRAINEE,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            '/api/auth/create-user/',
            {
                'username': 'kunal',
                'email': 'kunal@institution.edu',
                'password': 'password123',
                'role': User.Role.TRAINEE,
                'employee_id': '2345678',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['employee_id'], '2345678')

    def test_invite_attaches_trainee_to_batch(self):
        self.client.force_authenticate(self.faculty)
        batch = Batch.objects.create(name='DRF Batch 12', faculty=self.faculty)
        response = self.client.post(
            '/api/auth/invite/',
            {
                'email': 'ravi@institution.edu',
                'role': User.Role.TRAINEE,
                'first_name': 'Ravi',
                'employee_id': '2345678',
                'batch_id': batch.id,
                'send_email': False,
                'password': 'password123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(batch.trainees.filter(email='ravi@institution.edu').exists())
        self.assertNotIn('temporary_password', response.data)
        self.assertTrue(AuditEvent.objects.filter(action='user-invited').exists())

    @override_settings(MAILERS={'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}})
    def test_invite_emails_temporary_password_without_returning_it(self):
        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            '/api/auth/invite/',
            {
                'email': 'new-trainee@institution.edu',
                'role': User.Role.TRAINEE,
                'password': 'temporary123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('temporary_password', response.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('temporary123', mail.outbox[0].body)

    def test_user_list_is_filtered_to_faculty_batches(self):
        batch = Batch.objects.create(name='Own', faculty=self.faculty)
        other_batch = Batch.objects.create(name='Other', faculty=self.ta)
        own_trainee = User.objects.create_user(
            username='own-trainee', password='password123', role=User.Role.TRAINEE,
        )
        other_trainee = User.objects.create_user(
            username='other-trainee', password='password123', role=User.Role.TRAINEE,
        )
        batch.trainees.add(own_trainee)
        other_batch.trainees.add(other_trainee)

        self.client.force_authenticate(self.faculty)
        response = self.client.get('/api/auth/users/', {'batch_id': batch.id})
        self.assertEqual(response.status_code, 200)
        usernames = [row['username'] for row in response.data['results']]
        self.assertEqual(usernames, ['own-trainee'])

    def test_invite_rejects_foreign_batch(self):
        other = User.objects.create_user(
            username='otherfac',
            password='password123',
            role=User.Role.FACULTY,
        )
        batch = Batch.objects.create(name='Other', faculty=other)
        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            '/api/auth/invite/',
            {
                'email': 'x@institution.edu',
                'role': User.Role.TRAINEE,
                'batch_id': batch.id,
                'send_email': False,
                'password': 'password123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 403)
