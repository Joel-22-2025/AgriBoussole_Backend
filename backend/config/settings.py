"""
Django settings for config project.
"""


from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1,testserver,.onrender.com',
    cast=Csv(),
)

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third parties
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_spectacular',
    # Applications locales
    'accounts',
    'structures',
    'engagement',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
# Par défaut SQLite pour le développement local et les tests.
# En production, définir DB_ENGINE=django.db.backends.postgresql + les variables DB_*.
DB_ENGINE = config('DB_ENGINE', default='django.db.backends.sqlite3')
DATABASE_URL = config('DATABASE_URL', default='')

if DATABASE_URL:
    # Render fournit directement DATABASE_URL pour PostgreSQL.
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            ssl_require=DATABASE_URL.startswith(('postgres://', 'postgresql://')),
        )
    }
elif DB_ENGINE == 'django.db.backends.postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME'),
            'USER': config('DB_USER'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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

# Modèle utilisateur personnalisé
AUTH_USER_MODEL = 'accounts.User'

# Internationalisation
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Abidjan'
USE_I18N = True
USE_TZ = True

# Fichiers statiques et médias
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}
WHITENOISE_AUTOREFRESH = DEBUG

# Sécurité derrière le proxy Render / HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================================================
# Django REST Framework
# ============================================================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/minute',
        'user': '100/minute',
        'login': '5/minute',
        'register': '5/minute',
        'password_reset': '5/minute',
        'ai': '10/minute',
    },
    'EXCEPTION_HANDLER': 'config.exceptions.custom_exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ============================================================================
# JWT (simplejwt)
# Access : 15 minutes | Refresh : 7 jours | Rotation + blacklist
# ============================================================================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'TOKEN_OBTAIN_SERIALIZER': 'accounts.tokens.SaeiTokenObtainPairSerializer',
    'TOKEN_REFRESH_SERIALIZER': 'rest_framework_simplejwt.serializers.TokenRefreshSerializer',
    'TOKEN_VERIFY_SERIALIZER': 'rest_framework_simplejwt.serializers.TokenVerifySerializer',
    'TOKEN_BLACKLIST_SERIALIZER': 'rest_framework_simplejwt.serializers.TokenBlacklistSerializer',
}

# ============================================================================
# CORS
# ============================================================================
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=True, cast=bool)
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='', cast=Csv())
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

# ============================================================================
# drf-spectacular (OpenAPI)
# ============================================================================
SPECTACULAR_SETTINGS = {
    'TITLE': 'SAEI Orientation API',
    'DESCRIPTION': (
        "API d'orientation des entrepreneurs agri-agro vers les structures "
        "d'accompagnement (SAEI) au Bénin, au Sénégal et en Côte d'Ivoire."
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# ============================================================================
# Assistant IA — clé Groq (variable historique `cley_grok` dans le .env local)
# ============================================================================
GROQ_API_KEY = config('GROQ_API_KEY', default='') or config('cley_grok', default='')

# ============================================================================
# Email (backend console en développement)
# ============================================================================
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='saei-orientation@example.com')
ADMIN_EMAIL = config('ADMIN_EMAIL', default='admin@example.com')

EMAIL_HOST = config('EMAIL_HOST', default='')
if EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)

# ============================================================================
# Super administrateur par défaut (variables d'environnement uniquement)
# ============================================================================
DEFAULT_SUPERADMIN_EMAIL = config('DEFAULT_SUPERADMIN_EMAIL', default='')
DEFAULT_SUPERADMIN_PASSWORD = config('DEFAULT_SUPERADMIN_PASSWORD', default='')



ALLOWED_HOSTS = [
    "agriboussole-backend.onrender.com",
    "localhost",
    "127.0.0.1",
]