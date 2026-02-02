"""
Proxy loader for the real installed `celery` package.

This module used to be named `celery.py` and it shadowed the external
`celery` package. Keeping a proxy under a different name avoids import
shadowing while still providing a helper for environments where the
packaged `celery` isn't discovered normally.
"""
import sys
import os
import importlib.util


def _load_installed_celery():
    # Look for a 'celery' package directory in sys.path that is not the project root
    project_root = os.path.dirname(__file__)
    for p in sys.path:
        if not p:
            continue
        # Skip the project root so we don't re-import this file
        try:
            if os.path.abspath(p) == os.path.abspath(project_root):
                continue
        except Exception:
            pass

        candidate = os.path.join(p, 'celery')
        init_py = os.path.join(candidate, '__init__.py')
        if os.path.isdir(candidate) and os.path.isfile(init_py):
            # Load the installed celery package under the canonical name 'celery'
            spec = importlib.util.spec_from_file_location('celery', init_py)
            module = importlib.util.module_from_spec(spec)
            # Insert into sys.modules so relative imports inside the package work
            sys.modules['celery'] = module
            try:
                spec.loader.exec_module(module)
            except Exception:
                # If loading fails, remove from sys.modules to avoid inconsistent state
                sys.modules.pop('celery', None)
                raise
            return module

    raise ImportError('Could not find installed celery package in sys.path')


_real_celery = _load_installed_celery()

# Re-export public attributes from the real celery package
for _name in dir(_real_celery):
    if _name.startswith('_'):
        continue
    globals()[_name] = getattr(_real_celery, _name)

# Keep a reference to the loaded module
__real_celery_module__ = _real_celery
