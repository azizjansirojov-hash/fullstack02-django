"""Logging filters for generation job structured output."""


class GenerationContextFilter:
    """Ensure book_id / job_id exist on log records for the structured formatter."""

    def filter(self, record):
        if not hasattr(record, 'book_id'):
            record.book_id = '-'
        if not hasattr(record, 'job_id'):
            record.job_id = '-'
        return True
