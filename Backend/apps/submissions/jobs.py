"""Small in-process worker pool for MVP background processing."""

from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from django.db import close_old_connections

from .models import Submission
from .processing_service import process_submission


_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='submission-processor')
_lock = Lock()
_pending = set()


def start_processing(submission):
    with _lock:
        if submission.id in _pending:
            return False
        _pending.add(submission.id)
    submission.status = Submission.Status.PROCESSING
    submission.processing_error = ''
    submission.save(update_fields=['status', 'processing_error', 'updated_at'])
    try:
        future = _executor.submit(_run_processing, submission.id)
    except Exception:
        with _lock:
            _pending.discard(submission.id)
        submission.status = Submission.Status.FAILED
        submission.processing_error = 'Background processing could not be started.'
        submission.save(update_fields=['status', 'processing_error', 'updated_at'])
        raise
    future.add_done_callback(lambda _: _remove_pending(submission.id))
    return True


def submit_background(key, function, *args):
    """Schedule a keyed job on the same lightweight worker pool as submissions."""
    with _lock:
        if key in _pending:
            return False
        _pending.add(key)
    try:
        _executor.submit(_run_scheduled, key, function, args)
    except Exception:
        with _lock:
            _pending.discard(key)
        raise
    return True


def _remove_pending(submission_id):
    with _lock:
        _pending.discard(submission_id)


def _run_processing(submission_id):
    close_old_connections()
    try:
        process_submission(submission_id)
    finally:
        close_old_connections()


def _run_scheduled(key, function, args):
    close_old_connections()
    try:
        function(*args)
    finally:
        close_old_connections()
        _remove_pending(key)

