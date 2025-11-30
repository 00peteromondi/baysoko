"""
Compatibility shim to make `listings.tests` behave as a package during
unittest discovery. Previously the project had a top-level module at
`listings/tests.py` as well as a `listings/tests/` package which caused
unittest discovery to raise an ImportError (module vs package conflict).

This file sets `__path__` to point to the `listings/tests` directory so
Python treats `listings.tests` as a package and discovers tests inside
`listings/tests/*.py` normally.

Keep this shim minimal and safe.
"""
import os

# Ensure the package path includes the tests directory so discovery finds
# the test modules inside `listings/tests/`.
__path__ = [os.path.join(os.path.dirname(__file__), 'tests')]
