from pathlib import Path
from api.utils import generate_new_django_key, get_app_data_dir, load_env_vars, write_env_vars
import os
import sys

# for loading OCR models saved within the app code file
def get_app_base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent # desktop app 
    else:
        return Path(__file__).resolve().parent.parent # dev
BASE_DIR = get_app_base_dir()

# for dotenv loading
DATA_DIR = get_app_data_dir()


env_vars = load_env_vars()

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# will create secret key if it doesn't exist alr
if not env_vars.get("DJANGO_SECRET_KEY", ""): 
    new_key = generate_new_django_key()
    d = dict(DJANGO_SECRET_KEY = new_key)
    write_env_vars(d)

SECRET_KEY = env_vars.get("DJANGO_SECRET_KEY", "django-insecure-desktop-app-fallback-key")

# debug logic
IS_FROZEN = getattr(sys, 'frozen', False)
DEBUG = not IS_FROZEN 
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]


# Application definition
INSTALLED_APPS = [
    'api.apps.ApiConfig',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_q',

    'corsheaders',
    'storages',
    'social_django',
    'rest_framework_simplejwt.token_blacklist'
]

SITE_ID = 1


SESSION_COOKIE_SECURE = False

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'social_django.middleware.SocialAuthExceptionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

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

WSGI_APPLICATION = 'backend.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DATA_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/Chicago'

USE_I18N = True

USE_TZ = True

CORS_ALLOW_CREDENTIALS  = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
]


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


SESSION_COOKIE_SAMESITE = "Lax"

MEDIA_ROOT = DATA_DIR / "media"
MEDIA_URL = '/media/'
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)


STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }   

# Django Q config
Q_CLUSTER = {
    'name': 'DjangORM',
    'workers': 4 if not IS_FROZEN else 1, # conservative in prod
    'sync': False,
    'recycle': 500,
    'timeout': 600, 
    'retry': 720,
    'compress': True,
    'save_limit': 250,
    'queue_limit': 500,
    'cpu_affinity': 1,
    'label': 'Django Q',
    'orm': 'default',  
}