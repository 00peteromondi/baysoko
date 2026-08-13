# Payment logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'payment': {
            'format': '{levelname} {asctime} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'payment_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/payment.log',
            'formatter': 'payment',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': 'logs/error.log',
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
        },
    },
    'loggers': {
        'storefront.payment': {
            'handlers': ['payment_file', 'mail_admins'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}