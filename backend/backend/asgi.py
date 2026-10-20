"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

from pathlib import Path
import os
import socket
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------
# Core settings
# ------------------------------------------------------------------

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-ha_7q46x6xv0z!*b!-_v=60%2=ji!0$#&6r^x#7)sgdphx2fos",
)

DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# FIXED: added localhost / 127.0.0.1 so the backend can also be run locally.
ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "*.onrender.com,.onrender.com,localhost,127.0.0.1",
).split(",")


# ------------------------------------------------------------------
# Applications
# ------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # "whitenoise.runserver_nostatic",  <-- REMOVED: No longer needed with Supabase
    "corsheaders",
    "rest_framework",
    "accounts",
    "documents",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    # "whitenoise.middleware.WhiteNoiseMiddleware",  <-- REMOVED: No longer needed
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"


# ------------------------------------------------------------------
# Database
# ------------------------------------------------------------------

if os.getenv("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.parse(os.getenv("DATABASE_URL"), conn_max_age=600)
    }
    DATABASES["default"]["ENGINE"] = "django.db.backends.postgresql"
    DATABASES["default"].pop("OPTIONS", None)
    DATABASES["default"].setdefault("OPTIONS", {})["sslmode"] = "require"
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB"),
            "USER": os.getenv("POSTGRES_USER"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
            "HOST": "db",
            "PORT": 5432,
        }
    }


# ------------------------------------------------------------------
# Auth
# ------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accounts.User"


# ------------------------------------------------------------------
# I18N / TZ
# ------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# ------------------------------------------------------------------
# Static / media / Supabase Storage
# ------------------------------------------------------------------

# Supabase Credentials (Set these in Render Environment Variables)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
SUPABASE_BUCKET = os.getenv('SUPABASE_BUCKET', 'media')

# Bucket names (Optional: defaults to SUPABASE_BUCKET or 'media'/'static')
SUPABASE_MEDIA_BUCKET = os.getenv('SUPABASE_MEDIA_BUCKET', 'media')
SUPABASE_STATIC_BUCKET = os.getenv('SUPABASE_STATIC_BUCKET', 'static')

# Django 4.2+ Storage Configuration
STORAGES = {
    "default": {
        "BACKEND": "django_supabase_storage.SupabaseMediaStorage",
    },
    "staticfiles": {
        "BACKEND": "django_supabase_storage.SupabaseStaticStorage",
    },
}

# These are still needed by Django internally, even if Supabase serves the files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# REMOVED: STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
# REMOVED: WHITENOISE_USE_FINDERS = True


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ------------------------------------------------------------------
# Certificate verification helpers
# ------------------------------------------------------------------

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", f"http://{socket.gethostname()}:8000")
CERT_FRONTEND_URL = os.getenv("CERT_FRONTEND_URL")


# ------------------------------------------------------------------
# CORS — FIXED
# ------------------------------------------------------------------
# A wildcard origin CANNOT be combined with credentials (browsers reject it).
# List every origin that will call the API with cookies.

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = [
    # Vercel deployment
    "https://oauther-fqj8.vercel.app",
    # Local dev — Vite
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # Local dev — CRA / Next
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Allow the CSRF cookie to be readable from JS (needed to send X-CSRFToken).
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]


# ------------------------------------------------------------------
# CSRF — FIXED
# ------------------------------------------------------------------
# Same origins as CORS, plus the deployed HTTPS frontend.

CSRF_TRUSTED_ORIGINS = [
    "https://oauther-fqj8.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


# ------------------------------------------------------------------
# Session / CSRF cookie flags — FIXED
# ------------------------------------------------------------------
# Local dev (DEBUG=True):  SameSite=Lax, Secure=False
#   -> cookies flow between http://localhost:5173 and http://localhost:8000
#      without third-party-cookie blocking.
# Deployed (DEBUG=False): SameSite=None, Secure=True
#   -> required for the cross-site HTTPS Vercel frontend.

if DEBUG:
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SECURE = False
else:
    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SAMESITE = "None"
    CSRF_COOKIE_SECURE = True

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False   # must be readable from JS to send X-CSRFToken
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 1 week

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

application = get_asgi_application()
