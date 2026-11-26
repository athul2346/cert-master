FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Do NOT run migrate or collectstatic here: the database and Supabase
# credentials are not available at image-build time. Static collection runs
# in Render's pre-deploy phase (see render.yaml); migrations run at container
# start and are idempotent, which also keeps local docker-compose working.

# Never run the web process as root.
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Render provides WEB_CONCURRENCY if you want to tune workers.
CMD sh -c "python manage.py migrate --noinput && exec gunicorn backend.wsgi:application --bind 0.0.0.0:8000 --workers ${WEB_CONCURRENCY:-2} --timeout 120 --access-logfile - --error-logfile -"
