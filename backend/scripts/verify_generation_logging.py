"""Trigger a GenerationJob failure and print structured log evidence."""
import logging
import os
import sys
from io import StringIO
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from library.jobs import run_job  # noqa: E402
from library.models import Book, GenerationJob  # noqa: E402


def main():
    Book.objects.filter(slug='obs-log-book').delete()
    book = Book.objects.create(
        author_name='Observability',
        slug='obs-log-book',
        rights_status=Book.RightsStatus.PENDING_CLEARANCE,
    )
    job = GenerationJob.objects.create(
        book=book,
        job_type=GenerationJob.JobType.ALL,
        status=GenerationJob.Status.QUEUED,
    )

    buffer = StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(
        logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s book_id=%(book_id)s job_id=%(job_id)s %(message)s'
        )
    )
    jobs_logger = logging.getLogger('library.jobs')
    jobs_logger.addHandler(handler)
    jobs_logger.setLevel(logging.INFO)

    try:
        run_job(job)
    finally:
        jobs_logger.removeHandler(handler)

    job.refresh_from_db()
    output = buffer.getvalue()
    print('--- GenerationJob failure observability evidence ---')
    print('job_status:', job.status)
    print('error_message:', job.error_message)
    print('structured_log_line:')
    print(output.strip() or '(no log line captured)')
    return 0 if 'book_id=' in output and 'job_id=' in output else 1


if __name__ == '__main__':
    raise SystemExit(main())
