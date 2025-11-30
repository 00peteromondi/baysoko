import importlib
import sys
import json

print('--- sys.path ---')
print(json.dumps(sys.path))

try:
    m = importlib.import_module('tests')
    print('tests module file:', getattr(m, '__file__', repr(m)))
except Exception as e:
    print('import tests failed:', repr(e))
