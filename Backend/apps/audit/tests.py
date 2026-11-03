from django.test import TestCase

# Create your tests here.
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.batches.models import Batch
from apps.audit.models import AuditEvent


class AuditEventAPITests(APITestCase):
    def setUp(self):
        self.faculty = User.objects.create_user(username='faculty-audit', password='pass12345', role=User.Role.FACULTY)
        self.ta = User.objects.create_user(username='ta-audit', password='pass12345', role=User.Role.TA)
        self.trainee = User.objects.create_user(username='trainee-audit', password='pass12345', role=User.Role.TRAINEE)
        self.own_batch = Batch.objects.create(name='Owned batch', faculty=self.faculty)
        self.other_faculty = User.objects.create_user(username='other-faculty', password='pass12345', role=User.Role.FACULTY)
        self.other_batch = Batch.objects.create(name='Other batch', faculty=self.other_faculty)
        self.own_batch.tas.add(self.ta)
        AuditEvent.objects.create(actor=self.faculty, action='batch-created', target='Owned batch', batch=self.own_batch)
        AuditEvent.objects.create(actor=self.other_faculty, action='batch-created', target='Other batch', batch=self.other_batch)

    def test_faculty_and_assigned_ta_see_only_scoped_events(self):
        self.client.force_authenticate(self.faculty)
        faculty_rows = self.client.get('/api/audit-events/').data['results']
        self.assertEqual([row['target'] for row in faculty_rows], ['Owned batch'])
        self.client.force_authenticate(self.ta)
        ta_rows = self.client.get('/api/audit-events/').data['results']
        self.assertEqual([row['target'] for row in ta_rows], ['Owned batch'])

    def test_trainees_cannot_read_audit_events(self):
        self.client.force_authenticate(self.trainee)
        response = self.client.get('/api/audit-events/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
