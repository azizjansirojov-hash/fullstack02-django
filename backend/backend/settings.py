"""
Django settings for backend project.

Secrets and environment-dependent values come from environment / .env
(see .env.example). DEBUG defaults to False.
"""

from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1', 'testserver']),
    CSRF_TRUSTED_ORIGINS=(list, []),
)

environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1', 'testserver'])

_WEAK_SECRET_MARKERS = (
    'change-me',
    'docker-build-secret',
    'insecure',
    'django-insecure',
)
if not SECRET_KEY or any(m in SECRET_KEY.lower() for m in _WEAK_SECRET_MARKERS):
    if not DEBUG:
        raise ImproperlyConfigured(
            'SECRET_KEY must be set to a long random value in production. '
            'See backend/.env.example and DEPLOY.md.'
        )

if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    if not DEBUG:
        raise ImproperlyConfigured(
            'ALLOWED_HOSTS must be an explicit host list in production '
            '(wildcard * is not allowed). See DEPLOY.md.'
        )

INSTALLED_APPS = [
    # First so library.management.commands.runserver wins over staticfiles
    'library.apps.LibraryConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'users.apps.UsersConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'library.context_processors.spa_urls',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

# Database: DATABASE_URL or SQLite default
if env('DATABASE_URL', default=None):
    DATABASES = {'default': env.db('DATABASE_URL')}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {
                # Avoid "database is locked" during brief concurrent writes
                # (admin save + background PDF/TTS status updates).
                'timeout': 30,
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'uz'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = Path(env('STATIC_ROOT', default=str(BASE_DIR / 'staticfiles')))

MEDIA_URL = 'media/'
MEDIA_ROOT = Path(env('MEDIA_ROOT', default=str(BASE_DIR / 'media')))

# Built React SPA (same-origin production). Empty = Vite-only local dev.
FRONTEND_DIST = env('FRONTEND_DIST', default='')
if FRONTEND_DIST:
    FRONTEND_DIST = Path(FRONTEND_DIST)
    if not FRONTEND_DIST.is_absolute():
        FRONTEND_DIST = (BASE_DIR.parent / FRONTEND_DIST).resolve()

# Django → SPA origin (mirror of VITE_DJANGO_ORIGIN on the frontend).
# Empty / "same" = same-origin relative URLs (Docker with FRONTEND_DIST).
# Local dual-stack default when FRONTEND_DIST is unset: Vite on :5173.
_spa_origin_env = env('SPA_ORIGIN', default=None)
if _spa_origin_env is None:
    SPA_ORIGIN = '' if FRONTEND_DIST else 'http://127.0.0.1:5173'
else:
    _spa_origin_raw = str(_spa_origin_env).strip().rstrip('/')
    SPA_ORIGIN = '' if _spa_origin_raw in ('', 'same') else _spa_origin_raw

_staticfiles_backend = (
    'django.contrib.staticfiles.storage.StaticFilesStorage'
    if DEBUG
    else 'whitenoise.storage.CompressedStaticFilesStorage'
)
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': _staticfiles_backend,
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'users:login'
LOGIN_REDIRECT_URL = 'library:catalog'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'users.authentication.JWTCookieAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'auth': '5/min',
        'password_reset': '5/min',
        'rights_report': '5/hour',
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'luma-default',
    }
}
_redis_url = env('REDIS_URL', default='')
if _redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _redis_url,
        }
    }

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    # Returning users stay signed in until logout (30 days refresh).
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

JWT_ACCESS_COOKIE_NAME = 'access_token'
JWT_REFRESH_COOKIE_NAME = 'refresh_token'
JWT_COOKIE_HTTPONLY = True
JWT_COOKIE_SECURE = not DEBUG
JWT_COOKIE_SAMESITE = 'Lax'
JWT_COOKIE_PATH = '/'

_csrf_default = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
]
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=_csrf_default)

# Email (password reset)
EMAIL_BACKEND = env(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend',
)
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@luma.local')
EMAIL_HOST = env('EMAIL_HOST', default='')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
ALLOW_CONSOLE_EMAIL = env.bool('ALLOW_CONSOLE_EMAIL', default=False)
RIGHTS_CONTACT_EMAIL = env('RIGHTS_CONTACT_EMAIL', default='')

_console_backends = {
    'django.core.mail.backends.console.EmailBackend',
    'django.core.mail.backends.locmem.EmailBackend',
}
if not DEBUG and EMAIL_BACKEND in _console_backends and not ALLOW_CONSOLE_EMAIL:
    raise ImproperlyConfigured(
        'Production (DEBUG=False) requires a real EMAIL_BACKEND (SMTP). '
        'Set EMAIL_HOST_* in .env, or ALLOW_CONSOLE_EMAIL=1 only for staging. '
        'See DEPLOY.md.'
    )

# TLS / cookie hardening. USE_TLS=0 for local DEBUG=False without HTTPS.
USE_TLS = env.bool('USE_TLS', default=not DEBUG)
if not DEBUG and USE_TLS:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=False)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = not DEBUG
    CSRF_COOKIE_SECURE = not DEBUG

# TTS provider: "edge" today; swap via TTS_PROVIDER without rewriting callers.
TTS_PROVIDER = env('TTS_PROVIDER', default='edge')
TTS_VOICE = env('TTS_VOICE', default='uz-UZ-MadinaNeural')

# Generation abuse controls
GENERATION_MAX_RUNNING = env.int('GENERATION_MAX_RUNNING', default=2)
GENERATION_REGENERATE_DAILY_LIMIT = env.int(
    'GENERATION_REGENERATE_DAILY_LIMIT', default=10
)
GENERATION_STALE_QUEUED_SECONDS = env.int(
    'GENERATION_STALE_QUEUED_SECONDS', default=300
)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'structured': {
            'format': (
                '%(asctime)s %(levelname)s %(name)s '
                'book_id=%(book_id)s job_id=%(job_id)s %(message)s'
            ),
        },
        'standard': {
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
        },
    },
    'filters': {
        'generation_context': {
            '()': 'library.log_filters.GenerationContextFilter',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
        'generation_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'structured',
            'filters': ['generation_context'],
        },
    },
    'loggers': {
        'library.jobs': {
            'handlers': ['generation_console'],
            'level': 'INFO',
            'propagate': False,
        },
        'library': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}
