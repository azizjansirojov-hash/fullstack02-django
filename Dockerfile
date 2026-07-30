# syntax=docker/dockerfile:1
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Empty = same-origin reader links (SPA and Django share :8000 in Docker).
ENV VITE_DJANGO_ORIGIN=
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/app/frontend/dist
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install from the hashed lockfile (requirements.txt remains the editable source).
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt

COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

WORKDIR /app/backend
# Build-only secrets for collectstatic (never used at runtime).
RUN mkdir -p media staticfiles \
    && SECRET_KEY=build-only-collectstatic-not-for-runtime \
       DEBUG=True \
       ALLOWED_HOSTS=localhost \
       ALLOW_CONSOLE_EMAIL=1 \
       python manage.py collectstatic --noinput

# Runtime must supply SECRET_KEY, ALLOWED_HOSTS, etc. via env / compose.
# Do not bake ALLOWED_HOSTS=* or a production SECRET_KEY into the image.
EXPOSE 8000
CMD ["gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
