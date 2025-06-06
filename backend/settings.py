
from pathlib import Path
import os
from datetime import timedelta
from firebase_admin import initialize_app
import firebase_admin
from firebase_admin import credentials
import dj_database_url
import os

#cloudinary to manage images and optimization
import cloudinary_storage
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if service_account_path is None:
    raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")

cred = credentials.Certificate(str(service_account_path))
FIREBASE_APP = firebase_admin.initialize_app(cred)


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-q0m=8zvj=y4hsi+we3s^o57&tad46fxoo(ody6i0d(h&wq^m6#'

#SECRET_KEY = os.environ.get("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

#DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = [
    'agrilink-backend-hjzl.onrender.com',
    'localhost', 
    '127.0.0.1',  
]

CSRF_TRUSTED_ORIGINS = [
    'https://agrilink-backend-hjzl.onrender.com',
]

# Application definition

INSTALLED_APPS = [
    "daphne",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "debug_toolbar",
    "corsheaders",
    # "Agri_Link",

    'rest_framework_simplejwt',
    'rest_framework',
    "fcm_django",
    'cloudinary_storage',
    'cloudinary',

    'Agri_Link.apps.AgriLinkConfig',
    'django_celery_beat',
    'django_celery_results'
]

# fcm push notifications
FCM_API_KEY = "BHaNASWk9yTUeQoBGRdCZ9RMvLs89WdF5DxXa9Ywp5S8UGjb9HMhrmQcq75zllWMkvYDYSkctdCmxGtjXqLzCmI"

FCM_DJANGO_SETTINGS = {
    # Use the default Firebase app unless you have specific requirements for different apps
    "DEFAULT_FIREBASE_APP": FIREBASE_APP,
    
    # Set to True if you want users to only have one active device at a time (useful for scenarios where you want to ensure one device gets notifications)
    "ONE_DEVICE_PER_USER": True,
    
    # This setting helps clean up the database by removing devices that can no longer receive notifications, improving performance over time
    "DELETE_INACTIVE_DEVICES": True,
}

# flutterwave payments
FLUTTERWAVE_PUPLIC_KEY = 'FLWPUBK_TEST-c06379bd28d6ccb8a503ce2ec36e68c4-X'
FLUTTERWAVE_SECRET_KEY = 'FLWSECK_TEST-823dbcdbcd999c1ce7d67270d628d090-X'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.common.CommonMiddleware',
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
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
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

ASGI_APPLICATION = "backend.asgi.application"

# CHANNEL_LAYERS = {
#     "default": {
#         "BACKEND": "channels_redis.core.RedisChannelLayer",
#         "CONFIG": {
#             "hosts": [("127.0.0.1", 6379)],
#         },
#     },
# }

CHANNEL_LAYERS = {
       'default':{
           'BACKEND':'channels.layers.InMemoryChannelLayer'
       }
}


DEFAULT_CHANNEL_LAYER = 'default'

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    # 'default': {
    #     'ENGINE': 'django.db.backends.sqlite3',
    #     'NAME': BASE_DIR / 'db.sqlite3',
    # }
    'default': dj_database_url.config(
        default='postgresql://agrilink_database_9t3f_user:gudLWI3nQxHWH3LBMLxk05y5aygr87rC@dpg-d103803ipnbc738fl04g-a.oregon-postgres.render.com/agrilink_database_9t3f'
       )
}

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'

   
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'Agri_Link.User'

CORS_ALLOWED_ORIGINS = [
      "http://localhost:5173",
     "http://localhost:5174",
     "https://agrilink-jfb9.onrender.com"
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 9,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(weeks=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=10),
    "ROTATE_REFRESH_TOKENS": True,

    "ALGORITHM": "HS256",  # Google uses RS256, not HS256
    "SIGNING_KEY": SECRET_KEY,

    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",

    "JTI_CLAIM": "jti",
    "LEEWAY": timedelta(minutes=5),  # Allow a small time difference
}

INTERNAL_IPS = [
    # ...
    "127.0.0.1",
    # ...
]

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': 'dnsx36nia',
    'API_KEY': '555558364391432',
    'API_SECRET': 'gHDioqg-d8yxJGaRmdzN1IbWOEc',
    'SECURE': 'TRUE'
}

# Explicitly configure Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_STORAGE['CLOUD_NAME'],
    api_key=CLOUDINARY_STORAGE['API_KEY'],
    api_secret=CLOUDINARY_STORAGE['API_SECRET'],
)

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Celery Configuration
CELERY_BROKER_URL = 'sqla+postgresql://agrlink_database_user:hmfg61c5ESeWQFri9DGTcg0F2P7dhcvA@dpg-cvg19et2ng1s73dakkkg-a.oregon-postgres.render.com/agrlink_database'
CELERY_RESULT_BACKEND = 'db+postgresql://agrlink_database_user:hmfg61c5ESeWQFri9DGTcg0F2P7dhcvA@dpg-cvg19et2ng1s73dakkkg-a.oregon-postgres.render.com/agrlink_database'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True  # Silence warning

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # or your email provider
EMAIL_PORT = 587  # or 465 for SSL
EMAIL_USE_TLS = True  # or False for SSL
EMAIL_HOST_USER = 'agrilink143@gmail.com'
EMAIL_HOST_PASSWORD = 'mmxj qbjf xpxn ceez'
