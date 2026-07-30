from django.conf import settings
from django.contrib.staticfiles.management.commands.runserver import (
    Command as StaticfilesRunserverCommand,
)
from django.utils.version import get_docs_version

import atexit
import os
import signal
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path


VITE_PORT = 5173


class Command(StaticfilesRunserverCommand):
    """
    Same as Django runserver (with staticfiles), plus optional Vite SPA.

    API still binds to addr:port (default 127.0.0.1:8000).
    Opens / reuses the UI at http://localhost:5173/ (npm run dev in frontend/).
    """

    help = (
        'Starts a lightweight web server for development and the Vite SPA '
        'on port 5173 when it is not already running.'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._vite_process = None

    def run(self, **options):
        # Only the reloader parent (or a non-reloader process) owns Vite.
        # The autoreload child has RUN_MAIN=true and must not spawn a second copy.
        manage_vite = (
            os.environ.get('RUN_MAIN') != 'true'
            and os.environ.get('SKIP_VITE_AUTOSTART') != '1'
        )
        if manage_vite:
            self._ensure_vite()
        try:
            super().run(**options)
        finally:
            if manage_vite:
                self._stop_vite()

    def on_bind(self, server_port):
        quit_command = 'CTRL-BREAK' if sys.platform == 'win32' else 'CONTROL-C'

        if self._raw_ipv6:
            addr = f'[{self.addr}]'
        elif self.addr == '0':
            addr = '0.0.0.0'
        else:
            addr = self.addr

        now = datetime.now().strftime('%B %d, %Y - %X')
        version = self.get_version()
        print(
            f'{now}\n'
            f'Django version {version}, using settings {settings.SETTINGS_MODULE!r}\n'
            f'React UI at http://localhost:{VITE_PORT}/\n'
            f'Django API (this process) at {self.protocol}://{addr}:{server_port}/\n'
            f'Quit the server with {quit_command}.',
            file=self.stdout,
            flush=True,
        )
        docs_version = get_docs_version()
        if os.environ.get('DJANGO_RUNSERVER_HIDE_WARNING') != 'true':
            self.stdout.write(
                self.style.WARNING(
                    'WARNING: This is a development server. Do not use it in a '
                    'production setting. Use a production WSGI or ASGI server '
                    'instead.\nFor more information on production servers see: '
                    f'https://docs.djangoproject.com/en/{docs_version}/howto/'
                    'deployment/'
                )
            )

    def _frontend_dir(self):
        return Path(settings.BASE_DIR).resolve().parent / 'frontend'

    def _port_open(self, port):
        # Vite may bind to 127.0.0.1 and/or ::1 when host is "localhost".
        targets = [
            (socket.AF_INET, ('127.0.0.1', port)),
            (socket.AF_INET6, ('::1', port)),
        ]
        for family, address in targets:
            try:
                with socket.socket(family, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.5)
                    if sock.connect_ex(address) == 0:
                        return True
            except OSError:
                continue
        return False

    def _ensure_vite(self):
        frontend = self._frontend_dir()
        if not (frontend / 'package.json').is_file():
            self.stdout.write(
                self.style.WARNING(
                    f'Vite frontend not found at {frontend}; skipping SPA startup.'
                )
            )
            return

        if self._port_open(VITE_PORT):
            self.stdout.write(
                self.style.SUCCESS(
                    f'Vite already running at http://localhost:{VITE_PORT}/'
                )
            )
            return

        npm = 'npm.cmd' if sys.platform == 'win32' else 'npm'
        try:
            self._vite_process = subprocess.Popen(
                [npm, 'run', 'dev'],
                cwd=str(frontend),
            )
        except FileNotFoundError:
            self.stderr.write(
                self.style.ERROR(
                    'npm not found; start the SPA manually with: '
                    f'cd {frontend} && npm run dev'
                )
            )
            self._vite_process = None
            return
        except OSError as exc:
            self.stderr.write(
                self.style.ERROR(f'Failed to start Vite: {exc}')
            )
            self._vite_process = None
            return

        atexit.register(self._stop_vite)
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting Vite at http://localhost:{VITE_PORT}/ '
                f'(pid {self._vite_process.pid})'
            )
        )
        try:
            self.stdout.flush()
        except Exception:
            pass

    def _stop_vite(self):
        process = self._vite_process
        if process is None:
            return
        self._vite_process = None

        if process.poll() is not None:
            return

        try:
            if sys.platform == 'win32':
                # Kill npm and its node/vite children as a tree.
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(process.pid)],
                    capture_output=True,
                    check=False,
                )
            else:
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        except OSError:
            try:
                process.kill()
            except OSError:
                pass
