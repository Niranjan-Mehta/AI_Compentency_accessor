import shutil
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pymupdf
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.batches.models import Batch
from apps.tasks.models import Task

from .models import Submission
from .processing import extract_pdf_documents, extract_repository_documents, split_documents
from .processing_service import process_submission
from .vector_store import close_chroma_client, get_collection, has_indexed_commit, index_chunks, retrieve_chunks


def pdf_upload(name='project.pdf', content=b'%PDF-1.7\nminimal test pdf'):
    return SimpleUploadedFile(name, content, content_type='application/pdf')


class SubmissionAPITests(APITestCase):
    def setUp(self):
        backend_root = Path(__file__).resolve().parents[2]
        media_root = backend_root / f'.submission-test-media-{uuid.uuid4().hex}'
        media_root.mkdir()
        self.addCleanup(shutil.rmtree, media_root)
        media_override = override_settings(MEDIA_ROOT=media_root)
        media_override.enable()
        self.addCleanup(media_override.disable)

        self.faculty = User.objects.create(username='faculty', role=User.Role.FACULTY)
        self.other_faculty = User.objects.create(username='other-faculty', role=User.Role.FACULTY)
        self.ta = User.objects.create(username='ta', role=User.Role.TA)
        self.other_ta = User.objects.create(username='other-ta', role=User.Role.TA)
        self.trainee = User.objects.create(username='trainee', role=User.Role.TRAINEE)
        self.other_trainee = User.objects.create(username='other-trainee', role=User.Role.TRAINEE)

        self.batch = Batch.objects.create(name='Faculty batch', faculty=self.faculty)
        self.batch.trainees.add(self.trainee)
        self.batch.tas.add(self.ta)
        self.other_batch = Batch.objects.create(name='Other batch', faculty=self.other_faculty)
        self.other_batch.trainees.add(self.other_trainee)
        self.other_batch.tas.add(self.other_ta)

        self.task = self.make_task(self.faculty, self.batch)
        self.other_task = self.make_task(self.other_faculty, self.other_batch)

    @staticmethod
    def make_task(faculty, batch, **kwargs):
        values = {
            'title': 'Project task',
            'description': 'Complete a project',
            'skill': 'Backend Development',
            'created_by': faculty,
            'status': Task.Status.ACTIVE,
            'require_pdf': True,
        }
        values.update(kwargs)
        task = Task.objects.create(**values)
        task.batches.add(batch)
        return task

    def submit(self, task=None, **overrides):
        payload = {
            'task': (task or self.task).id,
            'repository_url': 'https://code.example.org/team/project',
            'branch': 'main',
            'project_pdf': pdf_upload(),
        }
        payload.update(overrides)
        return self.client.post('/api/submissions/', payload, format='multipart')

    def create_submission(self, trainee=None, task=None, **kwargs):
        return Submission.objects.create(
            trainee=trainee or self.trainee,
            task=task or self.task,
            repository_url='https://code.example.org/team/project',
            project_pdf=None,
            **kwargs,
        )

    def test_successful_public_git_and_pdf_submission(self):
        self.client.force_authenticate(self.trainee)
        response = self.submit(commit_hash='a' * 40)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['task']['id'], self.task.id)
        self.assertEqual(response.data['repository_url'], 'https://code.example.org/team/project')
        self.assertEqual(response.data['branch'], 'main')
        self.assertEqual(response.data['status'], Submission.Status.SUBMITTED)
        self.assertTrue(response.data['has_pdf'])
        self.assertNotIn('project_pdf', response.data)

        submission = Submission.objects.get(pk=response.data['id'])
        self.assertTrue(submission.project_pdf.name.startswith('submissions/pdfs/'))
        self.assertTrue(submission.project_pdf.name.endswith('.pdf'))

    def test_pdf_is_required_when_task_requires_it(self):
        self.client.force_authenticate(self.trainee)
        response = self.client.post(
            '/api/submissions/',
            {'task': self.task.id, 'repository_url': 'https://code.example.org/team/project'},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('project_pdf', response.data)

    def test_invalid_repository_urls_are_rejected(self):
        self.client.force_authenticate(self.trainee)
        invalid_urls = [
            'not-a-url',
            'http://code.example.org/team/project',
            'https://user:secret@code.example.org/team/project',
            'https://localhost/team/project',
        ]
        for repository_url in invalid_urls:
            with self.subTest(repository_url=repository_url):
                response = self.submit(repository_url=repository_url)
                self.assertEqual(response.status_code, 400)
                self.assertIn('repository_url', response.data)

    def test_invalid_pdf_extension_mime_and_signature_are_rejected(self):
        self.client.force_authenticate(self.trainee)
        invalid_files = [
            pdf_upload(name='project.txt'),
            SimpleUploadedFile('project.pdf', b'%PDF-1.7', content_type='text/plain'),
            pdf_upload(content=b'not a PDF file'),
        ]
        for uploaded in invalid_files:
            with self.subTest(name=uploaded.name, mime=uploaded.content_type):
                response = self.submit(project_pdf=uploaded)
                self.assertEqual(response.status_code, 400)
                self.assertIn('project_pdf', response.data)

    def test_size_limit_and_optional_pdf(self):
        self.client.force_authenticate(self.trainee)
        oversized = pdf_upload(content=b'%PDF-' + (b'x' * (10 * 1024 * 1024)))
        response = self.submit(project_pdf=oversized)
        self.assertEqual(response.status_code, 400)

        optional_task = self.make_task(
            self.faculty,
            self.batch,
            title='No PDF task',
            require_pdf=False,
        )
        response = self.client.post(
            '/api/submissions/',
            {
                'task': optional_task.id,
                'repository_url': 'https://code.example.org/team/no-pdf',
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data['has_pdf'])

    def test_resubmission_policy_and_historical_rows(self):
        self.client.force_authenticate(self.trainee)
        first = self.submit()
        self.assertEqual(first.status_code, 201)
        blocked = self.submit()
        self.assertEqual(blocked.status_code, 400)

        self.task.allow_resubmission = True
        self.task.save(update_fields=['allow_resubmission'])
        replacement = self.client.patch(
            f"/api/submissions/{first.data['id']}/",
            {
                'repository_url': 'https://code.example.org/team/revised-project',
                'project_pdf': pdf_upload(name='revised.pdf'),
            },
            format='multipart',
        )
        self.assertEqual(replacement.status_code, 200)
        self.assertNotEqual(replacement.data['id'], first.data['id'])
        self.assertEqual(Submission.objects.filter(trainee=self.trainee, task=self.task).count(), 2)
        self.assertFalse(Submission.objects.get(pk=first.data['id']).is_active)
        self.assertTrue(Submission.objects.get(pk=replacement.data['id']).is_active)

    def test_due_date_and_task_assignment_are_enforced(self):
        self.client.force_authenticate(self.other_trainee)
        response = self.submit(task=self.task)
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(self.trainee)
        self.task.due_date = timezone.now() - timedelta(minutes=1)
        self.task.save(update_fields=['due_date'])
        response = self.submit(task=self.task)
        self.assertEqual(response.status_code, 400)

    def test_trainees_only_list_and_retrieve_their_own_submissions(self):
        own = self.create_submission()
        other = self.create_submission(trainee=self.other_trainee, task=self.other_task)

        self.client.force_authenticate(self.trainee)
        listed = self.client.get('/api/submissions/')
        self.assertEqual([item['id'] for item in listed.data['results']], [own.id])
        self.assertEqual(self.client.get(f'/api/submissions/{own.id}/').status_code, 200)
        self.assertEqual(self.client.get(f'/api/submissions/{other.id}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/submissions/{other.id}/pdf/').status_code, 404)

    def test_faculty_and_ta_visibility_is_scoped_by_batches(self):
        own = self.create_submission()
        other = self.create_submission(trainee=self.other_trainee, task=self.other_task)

        self.client.force_authenticate(self.faculty)
        response = self.client.get('/api/submissions/', {'batch_id': self.batch.id})
        self.assertEqual([item['id'] for item in response.data['results']], [own.id])
        self.assertEqual(self.client.get(f'/api/submissions/{other.id}/').status_code, 404)

        self.client.force_authenticate(self.ta)
        response = self.client.get('/api/submissions/', {'task_id': self.task.id})
        self.assertEqual([item['id'] for item in response.data['results']], [own.id])
        self.assertEqual(self.client.get(f'/api/submissions/{other.id}/').status_code, 404)

        self.client.force_authenticate(self.other_ta)
        response = self.client.get('/api/submissions/')
        self.assertEqual([item['id'] for item in response.data['results']], [other.id])

    def test_submission_pdf_is_served_only_through_authorized_endpoint(self):
        self.client.force_authenticate(self.trainee)
        response = self.submit()
        submission_id = response.data['id']
        pdf_response = self.client.get(f'/api/submissions/{submission_id}/pdf/')
        self.assertEqual(pdf_response.status_code, 200)
        pdf_response.close()

        self.client.force_authenticate(self.other_trainee)
        self.assertEqual(self.client.get(f'/api/submissions/{submission_id}/pdf/').status_code, 404)

    def test_unauthenticated_and_staff_write_access_are_denied(self):
        response = self.submit()
        self.assertEqual(response.status_code, 401)

        self.client.force_authenticate(self.faculty)
        response = self.client.post('/api/submissions/', {}, format='multipart')
        self.assertEqual(response.status_code, 403)

    @override_settings(REPOSITORY_PROVIDER='gitea')
    def test_gitea_provider_can_be_selected_without_provider_specific_auth(self):
        self.client.force_authenticate(self.trainee)
        response = self.submit(repository_url='https://git.example.org/group/subgroup/project.git')
        self.assertEqual(response.status_code, 201)


def make_text_pdf(text):
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    content = document.tobytes()
    document.close()
    return content


class DeterministicEmbeddingProvider:
    def embed_documents(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * 32
            for char in text.lower():
                vector[ord(char) % len(vector)] += 1.0
            vectors.append(vector)
        return vectors


class PhaseFourProcessingTests(APITestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2]
        suffix = uuid.uuid4().hex
        self.media_root = root / f'.phase4-test-media-{suffix}'
        self.chroma_root = root / f'.phase4-test-chroma-{suffix}'
        self.work_root = root / f'.phase4-test-work-{suffix}'
        for directory in (self.media_root, self.chroma_root, self.work_root):
            directory.mkdir()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.chroma_root, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.work_root, ignore_errors=True)
        self.addCleanup(close_chroma_client, self.chroma_root)
        settings_override = override_settings(
            MEDIA_ROOT=self.media_root,
            CHROMA_PERSIST_DIRECTORY=self.chroma_root,
            REPOSITORY_WORK_ROOT=self.work_root,
            EMBEDDING_PROVIDER='http',
            EMBEDDING_DIMENSIONS=0,
        )
        settings_override.enable()
        self.addCleanup(settings_override.disable)

        self.faculty = User.objects.create(username='processing-faculty', role=User.Role.FACULTY)
        self.trainee = User.objects.create(username='processing-trainee', role=User.Role.TRAINEE)
        self.batch = Batch.objects.create(name='Processing batch', faculty=self.faculty)
        self.batch.trainees.add(self.trainee)
        self.task = SubmissionAPITests.make_task(self.faculty, self.batch, title='Processing task')
        self.submission = Submission.objects.create(
            trainee=self.trainee,
            task=self.task,
            repository_url='https://code.example.org/team/project',
            status=Submission.Status.PROCESSING,
        )

    def save_pdf(self, text='Architecture and implementation notes'):
        self.submission.project_pdf.save(
            'explanation.pdf',
            ContentFile(make_text_pdf(text)),
            save=True,
        )

    def test_pdf_extraction_and_empty_pdf_handling(self):
        self.save_pdf()
        documents = extract_pdf_documents(self.submission)
        self.assertIn('Architecture and implementation notes', documents[0].content)
        self.assertEqual(documents[0].metadata['source_type'], 'PDF')
        self.assertEqual(documents[0].metadata['page'], 1)

        self.submission.project_pdf.save('empty.pdf', ContentFile(b'%PDF-invalid'), save=True)
        with self.assertRaises(ValueError):
            extract_pdf_documents(self.submission)

    def test_source_extraction_skips_dependencies_and_binary_files(self):
        root = self.work_root / 'repo'
        (root / 'src').mkdir(parents=True)
        (root / 'node_modules' / 'package').mkdir(parents=True)
        (root / 'src' / 'app.py').write_text('def assess():\n    return "ready"\n', encoding='utf-8')
        (root / 'node_modules' / 'package' / 'bad.js').write_text('ignored()', encoding='utf-8')
        (root / 'src' / 'image.png').write_bytes(b'\x00binary')

        documents = extract_repository_documents(root)
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].metadata['file_path'], 'src/app.py')
        self.assertIn('return "ready"', documents[0].content)

    @override_settings(MAX_REPOSITORY_FILE_COUNT=1)
    def test_source_extraction_enforces_repository_file_count(self):
        root = self.work_root / 'many-files'
        root.mkdir()
        (root / 'one.py').write_text('first = 1', encoding='utf-8')
        (root / 'two.txt').write_text('second', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'configured limit'):
            extract_repository_documents(root)

    @patch('apps.submissions.repositories.public_git.PublicGitProvider._assert_public_destination')
    @patch('apps.submissions.repositories.public_git.subprocess.check_output', return_value='c' * 40)
    @patch('apps.submissions.repositories.public_git.subprocess.Popen')
    def test_git_provider_clones_selected_branch_without_shell(self, popen, check_output, _public_host):
        from .repositories.public_git import PublicGitProvider

        process = Mock()
        process.poll.return_value = 0
        process.returncode = 0
        popen.return_value = process
        destination = self.work_root / 'clone-target'
        commit = PublicGitProvider().clone_repository(
            'https://git.example.org/team/project.git',
            'feature/assessment',
            destination,
        )
        self.assertEqual(commit, 'c' * 40)
        command = popen.call_args.args[0]
        self.assertIn('--branch', command)
        self.assertIn('feature/assessment', command)
        self.assertFalse(popen.call_args.kwargs.get('shell', False))
        self.assertEqual(check_output.call_args.args[0][-2:], ['rev-parse', 'HEAD'])

    @patch('apps.submissions.repositories.public_git.socket.getaddrinfo')
    def test_git_provider_rejects_private_dns_resolution(self, resolve):
        from .repositories.public_git import PublicGitProvider

        resolve.return_value = [(None, None, None, None, ('127.0.0.1', 443))]
        with self.assertRaisesRegex(ValueError, 'private or internal'):
            PublicGitProvider._assert_public_destination('https://git.example.org/group/project')

    @override_settings(MAX_REPOSITORY_SIZE_BYTES=4)
    @patch('apps.submissions.repositories.public_git.PublicGitProvider._assert_public_destination')
    @patch('apps.submissions.repositories.public_git.subprocess.Popen')
    def test_git_provider_checks_size_after_fast_clone(self, popen, _public_host):
        from .repositories.public_git import PublicGitProvider

        destination = self.work_root / 'oversized-repository'
        process = Mock()
        process.poll.return_value = 0
        process.returncode = 0

        def clone_completed(*_args, **_kwargs):
            destination.mkdir()
            large_file = destination / 'large.bin'
            large_file.write_bytes(b'12345')
            large_file.chmod(0o444)
            return process

        popen.side_effect = clone_completed
        with self.assertRaisesRegex(ValueError, 'size limit'):
            PublicGitProvider().clone_repository(
                'https://git.example.org/group/project', 'main', destination,
            )
        self.assertFalse(destination.exists())

    def test_chunk_generation_preserves_file_path_and_line_ranges(self):
        from .processing import SourceDocument

        text = '\n'.join(f'line {number} has source context' for number in range(1, 30))
        chunks = split_documents([SourceDocument(text, {
            'source_type': 'CODE', 'file_path': 'src/module.py', 'file_extension': '.py',
        })], chunk_size=100, chunk_overlap=20)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.metadata['file_path'] == 'src/module.py' for chunk in chunks))
        self.assertTrue(all(chunk.metadata['start_line'] <= chunk.metadata['end_line'] for chunk in chunks))

    @patch('apps.submissions.vector_store.get_embedding_provider', return_value=DeterministicEmbeddingProvider())
    def test_vector_index_is_submission_scoped_and_duplicate_safe(self, _embedding):
        from .processing import ContentChunk

        chunks = [ContentChunk('private source snippet', {
            'source_type': 'CODE', 'file_path': 'src/private.py', 'file_extension': '.py',
            'start_line': 1, 'end_line': 1,
        })]
        count, duplicate = index_chunks(self.submission, 'a' * 40, chunks)
        self.assertEqual(count, 1)
        self.assertFalse(duplicate)
        self.submission.indexed_commit_hash = 'a' * 40
        self.assertTrue(has_indexed_commit(self.submission, 'a' * 40))
        self.assertEqual(index_chunks(self.submission, 'a' * 40, chunks), (1, True))

        other = Submission.objects.create(
            trainee=self.trainee,
            task=SubmissionAPITests.make_task(self.faculty, self.batch, title='Other processing task'),
            repository_url='https://code.example.org/team/other',
        )
        index_chunks(other, 'a' * 40, [type(chunks[0])('other private source', chunks[0].metadata)])
        other.indexed_commit_hash = 'a' * 40

        own_results = retrieve_chunks(self.submission, 'private source', source_type='CODE')
        other_results = retrieve_chunks(other, 'private source', source_type='CODE')
        self.assertTrue(own_results)
        self.assertTrue(all(item['metadata']['submission_id'] == str(self.submission.id) for item in own_results))
        self.assertTrue(all(item['metadata']['submission_id'] == str(other.id) for item in other_results))
        self.assertNotIn('other private source', [item['content'] for item in own_results])

    @patch('apps.submissions.vector_store.get_embedding_provider', return_value=DeterministicEmbeddingProvider())
    @patch('apps.submissions.processing_service.get_repository_provider')
    def test_processing_clones_extracts_indexes_and_records_commit(self, provider_factory, _embedding):
        self.save_pdf()
        commit = 'b' * 40

        def clone(_url, _branch, destination):
            destination.mkdir()
            (destination / 'main.ts').write_text('export const competency = "backend";\n', encoding='utf-8')
            return commit

        provider_factory.return_value.clone_repository.side_effect = clone
        process_submission(self.submission.id)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, Submission.Status.QUESTIONS_READY, self.submission.processing_error)
        self.assertEqual(self.submission.commit_hash, commit)
        self.assertEqual(self.submission.indexed_commit_hash, commit)
        self.assertIsNotNone(self.submission.processed_at)
        records = get_collection().get(where={'submission_id': str(self.submission.id)}, include=['metadatas'])
        types = {row['source_type'] for row in records['metadatas']}
        self.assertEqual(types, {'CODE', 'PDF'})
        self.assertEqual(list(self.work_root.iterdir()), [])

    @patch('apps.submissions.processing_service.get_repository_provider')
    def test_processing_failure_sets_failed_status_and_error(self, provider_factory):
        provider_factory.return_value.clone_repository.side_effect = ValueError('Repository clone timed out.')
        process_submission(self.submission.id)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, Submission.Status.FAILED)
        self.assertIn('timed out', self.submission.processing_error)

    @patch('apps.submissions.views.start_processing', return_value=True)
    def test_processing_api_allows_owner_and_exposes_status(self, _start):
        self.client.force_authenticate(self.faculty)
        response = self.client.post(f'/api/submissions/{self.submission.id}/process/')
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data['status'], Submission.Status.PROCESSING)
        status_response = self.client.get(f'/api/submissions/{self.submission.id}/processing-status/')
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.data['status'], Submission.Status.PROCESSING)

        self.client.force_authenticate(self.trainee)
        owner_start = self.client.post(f'/api/submissions/{self.submission.id}/process/')
        self.assertEqual(owner_start.status_code, 202)

        other_trainee = User.objects.create_user(
            username='processing-outsider', password='password123', role=User.Role.TRAINEE,
        )
        self.client.force_authenticate(other_trainee)
        denied = self.client.post(f'/api/submissions/{self.submission.id}/process/')
        self.assertEqual(denied.status_code, 404)
