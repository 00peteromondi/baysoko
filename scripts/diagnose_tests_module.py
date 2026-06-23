import importlib
import sys
import json

print('--- sys.path ---')
print(json.dumps(sys.path))

import importlib, sys, os

# Ensure project root is on sys.path so imports resolve the package correctly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print('--- sys.path ---')
print(sys.path)

def try_import(name):
    try:
        m = importlib.import_module(name)
        print(f"{name} ->", getattr(m, '__file__', repr(m)))
    except Exception as e:
        print(f"Failed to import {name}: {e}")

try_import('delivery')
try_import('delivery.tests')
try_import('tests')

print('\nModules ending with .tests loaded:')
for k in list(sys.modules.keys()):
    if k.endswith('.tests'):
        print(k, '->', getattr(sys.modules[k], '__file__', None))

print('\nFind packages with a tests.py file:')
for root, dirs, files in os.walk(PROJECT_ROOT):
    if 'tests.py' in files:
        print(os.path.relpath(os.path.join(root, 'tests.py'), PROJECT_ROOT))

print('\nDone')
