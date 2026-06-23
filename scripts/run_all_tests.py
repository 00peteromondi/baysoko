import os
import sys

# Ensure we're running from project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'baysoko.settings')

import django
from django.conf import settings
from django.core.management import call_command

django.setup()

BASE_DIR = getattr(settings, 'BASE_DIR', ROOT)

# Build list of local apps by checking for directories that match app label
local_apps = []
for app in settings.INSTALLED_APPS:
    label = app.split('.')[0]
    if label in ('django', 'crispy_forms', 'crispy_bootstrap5', 'cloudinary', 'cloudinary_storage', 'django_extensions', 'allauth'):
        continue
    app_path = os.path.join(str(BASE_DIR), label)
    if os.path.isdir(app_path):
        local_apps.append(label)

if not local_apps:
    local_apps = [a.split('.')[0] for a in settings.INSTALLED_APPS]

# Discover test modules under each local app and call them explicitly to avoid unittest discovery ambiguity
test_modules = []
for app in local_apps:
    tests_dir = os.path.join(str(BASE_DIR), app, 'tests')
    if os.path.isdir(tests_dir):
        for fname in os.listdir(tests_dir):
            if fname.startswith('test_') and fname.endswith('.py'):
                module_name = fname[:-3]
                test_modules.append(f"{app}.tests.{module_name}")

if not test_modules:
    # Fallback to running app labels
    print('No test modules found, running test runner for apps:', local_apps)
    call_command('test', *local_apps, verbosity=2)
else:
    print('Running test modules:', test_modules)
    call_command('test', *test_modules, verbosity=2)
