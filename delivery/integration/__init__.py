"""Compatibility shim for delivery.integration.

Some deployments have both `delivery/integration.py` and a `delivery/integration/` package
which causes `import delivery.integration` to resolve to the package instead of the module.
To be robust we expose a callable `create_delivery_from_order` that lazily loads the
implementation from delivery/integration.py at call time. This avoids import-time
errors and ensures the symbol is always importable.
"""
import os
import logging
import importlib.util

__all__ = [
    'create_delivery_from_order',
    'update_order_from_delivery',
    'sync_delivery_with_external_system',
    'get_available_delivery_services',
    'calculate_shipping_cost'
]

_module = None


def _load_impl():
    """Attempt to load the implementation from delivery/integration.py.

    On success the loaded module is stored in `_module` and subsequent
    attribute access will proxy to it.
    """
    global _module
    if _module is not None:
        return
    try:
        pkg_dir = os.path.dirname(__file__)
        integration_path = os.path.normpath(os.path.join(pkg_dir, '..', 'integration.py'))
        if os.path.exists(integration_path):
            spec = importlib.util.spec_from_file_location('delivery_integration_py', integration_path)
            mod = importlib.util.module_from_spec(spec)
            # Set package so relative imports inside the loaded file work (e.g. from .models import ...)
            mod.__package__ = 'delivery'
            spec.loader.exec_module(mod)
            _module = mod
        else:
            _module = None
    except Exception:
        logging.getLogger(__name__).exception('Failed to load delivery integration implementation')
        _module = None


def create_delivery_from_order(order):
    _load_impl()
    if _module is None:
        return None
    create = getattr(_module, 'create_delivery_from_order', None)
    if not create:
        return None
    return create(order)


def __getattr__(name):
    # Lazy-proxy other attributes to the loaded implementation module
    _load_impl()
    if _module is None:
        raise AttributeError(f"module 'delivery.integration' has no attribute '{name}'")
    attr = getattr(_module, name, None)
    if attr is None:
        raise AttributeError(f"module 'delivery.integration' has no attribute '{name}'")
    return attr
