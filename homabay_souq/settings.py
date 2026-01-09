import os
from pathlib import Path
import sys
from decouple import config, Csv
import cloudinary
import cloudinary.uploader
import cloudinary.api
import dj_database_url
from decimal import Decimal

# Force Django version compatibility
import django
if django.VERSION < (4, 2):
    raise RuntimeError("Django 4.2 or higher required")

BASE_DIR = Path(__file__).resolve().parent.parent

# Get database URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL and DATABASE_URL.strip():
    try:
        # Try to parse the DATABASE_URL
        db_config = dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)
        
        # Ensure all required fields are present
        if 'ENGINE' not in db_config:
            db_config['ENGINE'] = 'django.db.backends.postgresql'
        
        # Ensure PostgreSQL-specific settings
        db_config.setdefault('OPTIONS', {})
        
        DATABASES = {
            'default': db_config
        }
        
        print(f"✅ Using PostgreSQL database: {db_config.get('NAME', 'Unknown')}")
        print(f"✅ Database host: {db_config.get('HOST', 'Unknown')}")
        
    except Exception as e:
        print(f"⚠️  Error parsing DATABASE_URL: {e}")
        print("⚠️  Falling back to SQLite")
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
else:
    # Use SQLite for development
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    print("⚠️  Using SQLite for development - DATABASE_URL not set")



# Build paths inside the project like this: BASE_DIR / 'subdir'.


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-default-key-for-dev')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Normalize ALLOWED_HOSTS to a safe default if empty or misconfigured
try:
    # If Csv returned an empty list or list with empty string, replace with sensible defaults
    if not ALLOWED_HOSTS or (isinstance(ALLOWED_HOSTS, (list, tuple)) and all((not h) for h in ALLOWED_HOSTS)):
        ALLOWED_HOSTS = ['localhost', '127.0.0.1']
    # If a single string slipped through, wrap it
    if isinstance(ALLOWED_HOSTS, str):
        ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS.split(',') if h.strip()]
        if not ALLOWED_HOSTS:
            ALLOWED_HOSTS = ['localhost', '127.0.0.1']
except Exception:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Add Render external hostname
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    ALLOWED_HOSTS.append('homabaysouq.onrender.com')

# Cloudinary configuration - prefer python-decouple (reads .env) but allow CLOUDINARY_URL
# Use config() so values from `.env` are picked up in development when not exported to the shell
CLOUDINARY_CLOUD_NAME = config('CLOUDINARY_CLOUD_NAME', default='')
CLOUDINARY_API_KEY = config('CLOUDINARY_API_KEY', default='')
CLOUDINARY_API_SECRET = config('CLOUDINARY_API_SECRET', default='')
# Optional: allow full CLOUDINARY_URL (cloudinary://key:secret@name)
CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL', '')

# Only configure Cloudinary if credentials are provided
if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': CLOUDINARY_CLOUD_NAME,
        'API_KEY': CLOUDINARY_API_KEY,
        'API_SECRET': CLOUDINARY_API_SECRET,
    }
    # Also provide lowercase keys for compatibility with some versions/libraries
    CLOUDINARY_STORAGE.update({
        'cloud_name': CLOUDINARY_CLOUD_NAME,
        'api_key': CLOUDINARY_API_KEY,
        'api_secret': CLOUDINARY_API_SECRET,
    })
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    
    # Configure Cloudinary SDK
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET
    )
    print("✅ Cloudinary configured successfully")
else:
    # Fallback to local file storage
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    print("⚠️  Cloudinary not configured - using local file storage")

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
    'delivery.apps.DeliveryConfig',
    'channels',
    
    # Third-party apps
    'crispy_forms',
    'crispy_bootstrap5',
    'cloudinary',
    'cloudinary_storage',
    'django_extensions',
    'rest_framework',
    
    # Allauth apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    
    # Social providers
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
    
    # Local apps
    'users.apps.UsersConfig',
    'listings.apps.ListingsConfig',
    'chats.apps.ChatsConfig',
    'reviews.apps.ReviewsConfig',
    'blog.apps.BlogConfig',
    'notifications.apps.NotificationsConfig',
    'storefront.apps.StorefrontConfig',
]

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
}

# Custom user model
AUTH_USER_MODEL = 'users.User'

# Crispy forms configuration
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'homabay_souq.middleware.ClearCorruptedSessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'delivery.middleware.SellerStoreMiddleware',
    'notifications.middleware.NotificationsMiddleware',
]

ROOT_URLCONF = 'homabay_souq.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
            os.path.join(BASE_DIR, 'templates', 'account'),
            os.path.join(BASE_DIR, 'templates', 'socialaccount'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'listings.context_processors.cart_item_count',
                'listings.context_processors.cart_context',
                'chats.context_processors.messages_context',
                'notifications.context_processors.notifications_context',
                'delivery.context_processors.delivery_user_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'homabay_souq.wsgi.application'
# Database configuration - Robust version


# Password validation
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
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Create media directory if it doesn't exist
os.makedirs(MEDIA_ROOT, exist_ok=True)

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Channels (WebSocket) configuration - in-memory layer for development
ASGI_APPLICATION = 'homabay_souq.asgi.application'
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    }
}

# Login/Logout redirects
LOGIN_REDIRECT_URL = 'home'
LOGIN_URL = 'login'
LOGOUT_REDIRECT_URL = 'home'

# Security settings (configurable via environment). These default to
# secure values in production but remain permissive in development.
from django.core.exceptions import ImproperlyConfigured

# Enforce a strong SECRET_KEY in production
if not DEBUG:
    if SECRET_KEY.startswith('django-insecure') or len(SECRET_KEY) < 50:
        raise ImproperlyConfigured(
            'In production, set a strong SECRET_KEY via the SECRET_KEY environment variable.'
        )

# If running in development and SECRET_KEY is weak, generate a stable random one
# and persist it to a local file so it survives process reloads (avoids session corruption)
if DEBUG and (SECRET_KEY.startswith('django-insecure') or len(SECRET_KEY) < 50):
    SECRET_FILE = BASE_DIR / '.secret_key'
    try:
        if SECRET_FILE.exists():
            SECRET_KEY = SECRET_FILE.read_text().strip()
        else:
            from django.core.management.utils import get_random_secret_key
            new_key = get_random_secret_key()
            try:
                SECRET_FILE.write_text(new_key)
            except Exception:
                # If we can't write the file, still use the generated key in-memory
                pass
            SECRET_KEY = new_key
            print('⚠️  Generated and saved SECRET_KEY to .secret_key for development/testing')
    except Exception:
        try:
            from django.core.management.utils import get_random_secret_key
            SECRET_KEY = get_random_secret_key()
            print('⚠️  Using generated SECRET_KEY for development/testing (not persisted)')
        except Exception:
            pass

# HSTS settings
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=True, cast=bool)

# SSL / cookie settings (default to secure values; tests and localhost can
# still override them later)
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=True, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=True, cast=bool)

SECURE_BROWSER_XSS_FILTER = config('SECURE_BROWSER_XSS_FILTER', default=True, cast=bool)
SECURE_CONTENT_TYPE_NOSNIFF = config('SECURE_CONTENT_TYPE_NOSNIFF', default=True, cast=bool)

# When running tests, avoid enforcing HTTPS redirects which cause 301 responses
RUNNING_TESTS = len(sys.argv) > 1 and sys.argv[1] == 'test'
if RUNNING_TESTS:
    SECURE_SSL_REDIRECT = False
    # Ensure the Django test client host is allowed
    try:
        # ALLOWED_HOSTS may be a list from decouple Csv
        if isinstance(ALLOWED_HOSTS, (list, tuple)):
            if 'testserver' not in ALLOWED_HOSTS:
                ALLOWED_HOSTS.append('testserver')
        else:
            ALLOWED_HOSTS = list(ALLOWED_HOSTS) + ['testserver']
    except Exception:
        ALLOWED_HOSTS = ['testserver']

# Safety: if running on local hosts, ensure we do not redirect to HTTPS even if
# DEBUG is False in the environment. This prevents local webhook/testing clients
# from being redirected to HTTPS when the dev server isn't serving TLS.
try:
    hosts = ALLOWED_HOSTS if isinstance(ALLOWED_HOSTS, (list, tuple)) else [ALLOWED_HOSTS]
    # Only disable SSL redirect automatically for local development or tests
    if any(h in ('localhost', '127.0.0.1') for h in hosts) and (DEBUG or RUNNING_TESTS):
        SECURE_SSL_REDIRECT = False
except Exception:
    pass

# Ensure SSL redirect is enabled for deployment checks unless running tests
if RUNNING_TESTS:
    SECURE_SSL_REDIRECT = False
else:
    SECURE_SSL_REDIRECT = True

# Site ID
SITE_ID = 1
SITE_URL = config('SITE_URL', default='http://localhost:8000')

# OpenAI Configuration for AI Listing Assistant
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')

# Feature flag for AI listing assistant
AI_LISTING_ENABLED = bool(OPENAI_API_KEY)

# Delivery integration settings
# Controls whether Orders are automatically synchronized to DeliveryRequest
DELIVERY_AUTO_SYNC_ENABLED = config('DELIVERY_AUTO_SYNC_ENABLED', default=True, cast=bool)
# Controls whether Delivery status changes should update the originating Order
DELIVERY_UPDATE_ORDER_STATUS = config('DELIVERY_UPDATE_ORDER_STATUS', default=True, cast=bool)

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Allauth settings (updated to new configuration keys to avoid deprecation warnings)
# Use ACCOUNT_LOGIN_METHODS to specify allowed login methods (order-independent)
ACCOUNT_LOGIN_METHODS = {'email', 'username'}

# Configure required signup fields using the new ACCOUNT_SIGNUP_FIELDS pattern.
# Use '*' suffix to indicate a required field in the new configuration.
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']

# Keep email verification and uniqueness as configured
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_UNIQUE_EMAIL = True

# Social account settings
SOCIALACCOUNT_AUTO_SIGNUP = True  # Show signup form to collect additional data
SOCIALACCOUNT_EMAIL_VERIFICATION = 'optional'
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_STORE_TOKENS = True

# Disable the problematic 3rdparty signup if it's causing issues
SOCIALACCOUNT_ENABLED = True

# Login redirects
LOGIN_REDIRECT_URL = 'home'
ACCOUNT_LOGOUT_REDIRECT_URL = 'home'
SOCIALACCOUNT_LOGIN_ON_GET = False  # Show intermediate page
ACCOUNT_LOGOUT_ON_GET = True  # Logout immediately on GET request
# Social Auth Environment Variables
GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '')
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', '')
FACEBOOK_OAUTH_CLIENT_ID = os.environ.get('FACEBOOK_OAUTH_CLIENT_ID', '')
FACEBOOK_OAUTH_CLIENT_SECRET = os.environ.get('FACEBOOK_OAUTH_CLIENT_SECRET', '')

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
    },
    'facebook': {
        'METHOD': 'oauth2',
        'SCOPE': ['email', 'public_profile'],
        'AUTH_PARAMS': {'auth_type': 'reauthenticate'},
        'INIT_PARAMS': {'cookie': True},
        'FIELDS': [
            'id',
            'first_name',
            'last_name',
            'email',
        ],
        'EXCHANGE_TOKEN': True,
        'VERIFIED_EMAIL': False,
        'VERSION': 'v13.0',
    }
}

# Custom adapter
SOCIALACCOUNT_ADAPTER = 'users.adapters.CustomSocialAccountAdapter'
SOCIALACCOUNT_FORMS = {
    'signup': 'users.social_forms.CustomSocialSignupForm',
}

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')

# AI Listing Assistant flag
AI_LISTING_ENABLED = bool(OPENAI_API_KEY)

# Auto connect social accounts to existing users by email
SOCIALACCOUNT_AUTO_SIGNUP = True

AFRICASTALKING_USERNAME = os.environ.get('AFRICASTALKING_USERNAME', '')
AFRICASTALKING_API_KEY = os.environ.get('AFRICASTALKING_API_KEY', '')
SMS_ENABLED = os.environ.get('SMS_ENABLED', 'False').lower() == 'true'

# Delivery System Integration
# Delivery settings
DELIVERY_SYSTEM_ENABLED = config('DELIVERY_SYSTEM_ENABLED', default=True, cast=bool)
DELIVERY_SYSTEM_URL = config('DELIVERY_SYSTEM_URL', default='')
DELIVERY_SYSTEM_API_KEY = config('DELIVERY_SYSTEM_API_KEY', default='')
DELIVERY_WEBHOOK_KEY = config('DELIVERY_WEBHOOK_KEY', default='')

# Default pickup information
DEFAULT_PICKUP_ADDRESS = config('DEFAULT_PICKUP_ADDRESS', default='Main Store, HomaBay')
DEFAULT_PICKUP_PHONE = config('DEFAULT_PICKUP_PHONE', default='+254700000000')
DEFAULT_PICKUP_EMAIL = config('DEFAULT_PICKUP_EMAIL', default='store@homabaysouq.com')

# Delivery fee settings
BASE_DELIVERY_FEE = Decimal('100.00')
MAX_PACKAGE_WEIGHT = 100  # kg
MAX_PACKAGE_VOLUME = 1000000  # cubic cm (1 cubic meter)

# Google Maps API for distance calculation
GOOGLE_MAPS_API_KEY = config('GOOGLE_MAPS_API_KEY', default='')

# Delivery notification settings
ENABLE_EMAIL_NOTIFICATIONS = config('ENABLE_EMAIL_NOTIFICATIONS', default=True, cast=bool)
ENABLE_SMS_NOTIFICATIONS = config('ENABLE_SMS_NOTIFICATIONS', default=False, cast=bool)
# E-commerce platform configuration
ECOMMERCE_PLATFORM_NAME = config('ECOMMERCE_PLATFORM_NAME', default='HomaBay Souq')
ECOMMERCE_WEBHOOK_URL = config('ECOMMERCE_WEBHOOK_URL', default='http://localhost:8000/api/delivery/webhook/homabay-souq/')
# E-commerce platforms
ECOMMERCE_PLATFORMS = [
    {
        'name': 'HomaBay Souq',
        'platform_type': 'homabay_souq',
        'base_url': 'http://localhost:8000',
        'api_key': '',
        'webhook_secret': DELIVERY_WEBHOOK_KEY,
        'sync_enabled': True,
    }
]

# Email configuration (for production)
if not DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = 'HomaBay Souq <noreply@homabaysouq.com>'

    # Password reset timeout in seconds (24 hours)
    PASSWORD_RESET_TIMEOUT = 86400
    MPESA_CONSUMER_KEY = os.environ.get('MPESA_CONSUMER_KEY', '')
    MPESA_CONSUMER_SECRET = os.environ.get('MPESA_CONSUMER_SECRET', '')
    MPESA_ENVIRONMENT = os.environ.get('MPESA_ENVIRONMENT', 'production')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    # Email Configuration
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = 'HomaBay Souq <noreply@homabaysouq.com>'

    # Password reset timeout in seconds (24 hours)
    PASSWORD_RESET_TIMEOUT = 86400

# Import logging settings
from .logging_settings import LOGGING

# Ensure logs directory exists
import os
os.makedirs('logs', exist_ok=True)

# Additional security settings
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'

# Custom settings
HOMABAY_SOUQ = {
    'SITE_NAME': 'HomaBay Souq',
    'SITE_DESCRIPTION': 'Buy and sell with people in your Homabay community',
}

# Storefront configuration
STORE_FREE_LISTING_LIMIT = int(os.environ.get('STORE_FREE_LISTING_LIMIT', '5'))
# Maximum image upload size in megabytes
MAX_IMAGE_UPLOAD_SIZE_MB = int(os.environ.get('MAX_IMAGE_UPLOAD_SIZE_MB', '10'))
MAX_IMAGE_UPLOAD_SIZE = MAX_IMAGE_UPLOAD_SIZE_MB * 1024 * 1024



# Add to settings.py
MPESA_CONSUMER_KEY = os.environ.get('MPESA_CONSUMER_KEY', '')
MPESA_CONSUMER_SECRET = os.environ.get('MPESA_CONSUMER_SECRET', '')
MPESA_BUSINESS_SHORTCODE = os.environ.get('MPESA_BUSINESS_SHORTCODE', '')
MPESA_PASSKEY = os.environ.get('MPESA_PASSKEY', '')
# Use localhost for development, production URL for production
MPESA_CALLBACK_URL = os.environ.get('MPESA_CALLBACK_URL', '')
MPESA_ENVIRONMENT = os.environ.get('MPESA_ENVIRONMENT', 'sandbox')  # or 'production'

# How many remaining sellers (with unshipped items) should trigger reminder notifications
SELLER_SHIPMENT_REMINDER_THRESHOLD = int(os.environ.get('SELLER_SHIPMENT_REMINDER_THRESHOLD', '2'))

