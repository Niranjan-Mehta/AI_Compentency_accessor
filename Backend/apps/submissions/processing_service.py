"""Synchronous processing unit used by a lightweight background thread."""

import uuid
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .models import Submission
from .processing import extract_pdf_documents, extract_repository_documents, split_documents
from .repositories import get_repository_provider
from .repositories.filesystem import remove_repository_directory
from .vector_store import has_indexed_commit, index_chunks


def process_submission(submission_id):
    submission = Submission.objects.select_related('task').get(pk=submission_id)
    try:
        settings.REPOSITORY_WORK_ROOT.mkdir(parents=True, exist_ok=True)
        repository_path = settings.REPOSITORY_WORK_ROOT / f'submission-{submission.id}-{uuid.uuid4().hex}'
        try:
            provider = get_repository_provider()
            resolved_commit = provider.clone_repository(
                submission.repository_url,
                submission.branch,
                repository_path,
            )
            if has_indexed_commit(submission, resolved_commit):
                submission.commit_hash = resolved_commit
                submission.indexed_commit_hash = resolved_commit
                submission.status = Submission.Status.QUESTIONS_READY
                submission.processing_error = ''
                submission.processed_at = timezone.now()
                submission.save(update_fields=[
                    'commit_hash', 'indexed_commit_hash', 'status', 'processing_error',
                    'processed_at', 'updated_at',
                ])
                return

            documents = extract_repository_documents(repository_path)
            if submission.project_pdf:
                documents.extend(extract_pdf_documents(submission))
            chunks = split_documents(documents)
            index_chunks(submission, resolved_commit, chunks)
        finally:
            remove_repository_directory(repository_path)
        submission.commit_hash = resolved_commit
        submission.indexed_commit_hash = resolved_commit
        submission.status = Submission.Status.QUESTIONS_READY
        submission.processing_error = ''
        submission.processed_at = timezone.now()
        submission.save(update_fields=[
            'commit_hash', 'indexed_commit_hash', 'status', 'processing_error',
            'processed_at', 'updated_at',
        ])
    except Exception as exc:
        submission.status = Submission.Status.FAILED
        if isinstance(exc, (ValueError, RuntimeError)):
            message = str(exc).strip()
        else:
            message = 'Processing failed due to an internal error.'
        submission.processing_error = message[:1000] or 'Submission processing failed.'
        submission.save(update_fields=['status', 'processing_error', 'updated_at'])

