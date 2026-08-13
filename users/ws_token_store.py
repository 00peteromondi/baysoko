import time
import threading
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# In-memory fallback store for development when cache backend is unavailable.
_local_store = {}
_lock = threading.Lock()


def set_token(key, value, timeout=60):
    """Store token in cache, fall back to local store if cache unavailable."""
    try:
        cache.set(key, value, timeout=timeout)
        return True
    except Exception as e:
        logger.warning(f"Cache unavailable, using local store for {key}: {e}")
        expire_at = time.time() + (timeout or 60)
        with _lock:
            _local_store[key] = (value, expire_at)
        return False


def get_token(key):
    """Retrieve token value from cache or local fallback."""
    try:
        val = cache.get(key)
        if val is not None:
            return val
    except Exception as e:
        logger.debug(f"Cache get failed for {key}: {e}")

    # Fallback to local store
    with _lock:
        item = _local_store.get(key)
        if not item:
            return None
        value, expire_at = item
        if time.time() > expire_at:
            # expired
            try:
                del _local_store[key]
            except KeyError:
                pass
            return None
        return value


def delete_token(key):
    """Delete token from cache and local fallback."""
    try:
        cache.delete(key)
    except Exception:
        logger.debug(f"Cache delete failed for {key}, clearing local store")
    with _lock:
        try:
            del _local_store[key]
        except KeyError:
            pass
