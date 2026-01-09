import importlib, sys, pkgutil

print('sys.path:')
for p in sys.path[:5]:
    print('  ', p)

for name in ['delivery', 'delivery.tests', 'tests']:
    try:
        m = importlib.import_module(name)
        print(f"\nImported {name}: file={getattr(m,'__file__',None)} package={getattr(m,'__package__',None)} path={getattr(m,'__path__',None)}")
    except Exception as e:
        print(f"\nFailed to import {name}: {e}")

print('\nModules ending with .tests loaded:')
for k in sorted(sys.modules.keys()):
    if k.endswith('.tests'):
        mod = sys.modules[k]
        print(k, getattr(mod,'__file__',None), getattr(mod,'__path__',None))

print('\nFind packages with a tests.py file:')
for finder, modname, ispkg in pkgutil.iter_modules():
    pass

print('\nDone')
