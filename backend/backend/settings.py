from pathlib import Path
from dotenv import load_dotenv 
import os
import sys

# for dotenv loading
def get_app_path():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent # desktop app 
    else:
        return Path(__file__).resolve().parent.parent # dev

load_dotenv(get_app_path() / ".env")


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", 'django-insecure-desktop-app-fallback-key')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


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
        'NAME': BASE_DIR / 'db.sqlite3',
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

def get_media_root():
    if getattr(sys, 'frozen', False):
        app_name = "ResearchMarker"
        
        if sys.platform == "win32":
            base_path = Path(os.environ["APPDATA"]) / app_name
        elif sys.platform == "darwin":
            base_path = Path.home() / "Library" / "Application Support" / app_name
        else:
            base_path = Path.home() / ".local" / "share" / app_name
            
        media_path = base_path / "media"
        media_path.mkdir(parents=True, exist_ok=True)
        return media_path
    
    else:
        return BASE_DIR / "media"

MEDIA_ROOT = get_media_root()
MEDIA_URL = '/media/'


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
    'workers': 4,
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