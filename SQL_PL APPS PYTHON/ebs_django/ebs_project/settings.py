"""
Django settings for EBS R12 Explorer.
"""
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import os

# ==================== PATHS ====================
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ==================== SECURITY ====================
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-fallback-change-me")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

CSRF_TRUSTED_ORIGINS = [f"http://{h}" for h in ALLOWED_HOSTS if h not in ("0.0.0.0",)]
CSRF_TRUSTED_ORIGINS += [f"https://{h}" for h in ALLOWED_HOSTS if h not in ("0.0.0.0",)]

# ==================== APPLICATIONS ====================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',

    # Local
    'api',
]

# ==================== MIDDLEWARE ====================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'api.middleware.ActivityLogMiddleware',
]

ROOT_URLCONF = 'ebs_project.urls'

# ==================== TEMPLATES ====================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ebs_project.wsgi.application'

# ==================== DATABASE ====================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 30,
        },
    }
}

# ==================== AUTHENTICATION ====================
AUTH_USER_MODEL = 'api.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 6}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==================== INTERNATIONALIZATION ====================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ==================== STATIC & MEDIA ====================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "media"

# Create media subdirs on boot
for sub in ("data", "uploads", "backups"):
    (MEDIA_ROOT / sub).mkdir(parents=True, exist_ok=True)

# ==================== DEFAULT PRIMARY KEY ====================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==================== REST FRAMEWORK ====================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ),
    'EXCEPTION_HANDLER': 'api.utils.custom_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {},
}

# ==================== JWT ====================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "20"))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv("JWT_REFRESH_TOKEN_DAYS", "7"))),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# ==================== CORS ====================
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [f"http://{h}" for h in ALLOWED_HOSTS if h not in ("0.0.0.0",)]
CORS_ALLOW_CREDENTIALS = True

# ==================== UPLOAD ====================
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("MAX_UPLOAD_SIZE_MB", "5000")) * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB in RAM, rest to disk
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000

# ==================== SECURITY HEADERS ====================
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'SAMEORIGIN'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = False  # JS needs to read it
CSRF_COOKIE_SAMESITE = 'Lax'

if not DEBUG:
    SECURE_SSL_REDIRECT = False  # Change to True if behind HTTPS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# ==================== LOGGING ====================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '[{asctime}] {levelname} {name} :: {message}', 'style': '{'},
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'api': {'handlers': ['console'], 'level': 'DEBUG' if DEBUG else 'INFO', 'propagate': False},
    },
}
# ==================== EBS CONNECTOR ====================
EBS_SESSION_TTL = int(os.getenv("EBS_SESSION_TTL", "1200"))
EBS_MAX_CONNECTIONS_PER_USER = int(os.getenv("EBS_MAX_CONNECTIONS_PER_USER", "1"))
EBS_QUERY_TIMEOUT = int(os.getenv("EBS_QUERY_TIMEOUT", "300"))
EBS_MAX_ROWS = int(os.getenv("EBS_MAX_ROWS", "50000"))

# Encryption key for credentials (derived from SECRET_KEY)
import hashlib
EBS_ENCRYPTION_KEY = hashlib.sha256(SECRET_KEY.encode()).digest()

# ==================== EBS CONNECTOR ====================
EBS_SESSION_TTL = int(os.getenv("EBS_SESSION_TTL", "1200"))
EBS_MAX_CONNECTIONS_PER_USER = int(os.getenv("EBS_MAX_CONNECTIONS_PER_USER", "5"))
EBS_QUERY_TIMEOUT = int(os.getenv("EBS_QUERY_TIMEOUT", "300"))
EBS_MAX_ROWS = int(os.getenv("EBS_MAX_ROWS", "50000"))

import hashlib
EBS_ENCRYPTION_KEY = hashlib.sha256(SECRET_KEY.encode()).digest()