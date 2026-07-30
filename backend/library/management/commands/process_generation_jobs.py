"""Process durable GenerationJob rows (PDF / TTS)."""

from django.core.management.base import BaseCommand

from library.jobs import process_loop, process_one


class Command(BaseCommand):
    help = (
        'Process queued book media generation jobs. '
        'Use --loop in Docker/worker; omit for a single drain pass.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--loop',
            action='store_true',
            help='Poll forever for new jobs.',
        )
        parser.add_argument(
            '--poll',
            type=float,
            default=2.0,
            help='Seconds to sleep when idle in --loop mode (default 2).',
        )

    def handle(self, *args, **options):
        if options['loop']:
            self.stdout.write(self.style.SUCCESS('Generation worker started (--loop).'))
            process_loop(poll_seconds=options['poll'], once=False)
            return

        count = 0
        while process_one():
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Processed {count} job(s).'))
