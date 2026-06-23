import logging
import requests
from django.core.files.base import ContentFile
from django.utils.text import slugify
from io import BytesIO
from PIL import Image, UnidentifiedImageError

from listings.models import Listing, ListingImage

logger = logging.getLogger(__name__)

# Wikimedia Commons API endpoints
WIKIMEDIA_API = 'https://commons.wikimedia.org/w/api.php'


def search_wikimedia_images(query, max_results=3):
    """Search Wikimedia Commons file namespace for images matching query.
    Returns list of dicts with keys: title, pageid
    """
    params = {
        'action': 'query',
        'list': 'search',
        'format': 'json',
        'srsearch': query,
        'srnamespace': 6,  # File namespace
        'srlimit': max_results,
    }
    try:
        r = requests.get(WIKIMEDIA_API, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        hits = data.get('query', {}).get('search', [])
        return hits
    except Exception as e:
        logger.exception('Wikimedia search failed for %s: %s', query, e)
        return []


def get_imageinfo_for_pageids(pageids):
    params = {
        'action': 'query',
        'format': 'json',
        'prop': 'imageinfo',
        'iiprop': 'url|mime|size',
        'pageids': '|'.join(str(p) for p in pageids)
    }
    try:
        r = requests.get(WIKIMEDIA_API, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get('query', {}).get('pages', {})
    except Exception as e:
        logger.exception('Wikimedia imageinfo fetch failed: %s', e)
        return {}


def download_image(url, max_bytes=5 * 1024 * 1024):
    """Download image bytes with a size limit."""
    try:
        r = requests.get(url, stream=True, timeout=15)
        r.raise_for_status()
        content = BytesIO()
        total = 0
        for chunk in r.iter_content(8192):
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError('Image too large')
            content.write(chunk)
        return content.getvalue()
    except Exception as e:
        logger.exception('Failed to download image %s: %s', url, e)
        return None


def validate_image_bytes(img_bytes):
    try:
        im = Image.open(BytesIO(img_bytes))
        im.verify()
        return True
    except (UnidentifiedImageError, Exception) as e:
        logger.exception('Invalid image bytes: %s', e)
        return False


def save_image_to_listing(listing: Listing, img_bytes: bytes, filename=None, caption=None):
    try:
        if not filename:
            filename = slugify(listing.title)[:50] or 'listing'
            filename = f"{filename}.jpg"

        content_file = ContentFile(img_bytes)
        li = ListingImage(listing=listing)
        # Save via storage backend (CloudinaryField or ImageField both support .save)
        li.image.save(filename, content_file, save=False)
        if caption:
            li.caption = caption
        li.save()
        return li
    except Exception as e:
        logger.exception('Failed saving image to listing %s: %s', listing.id, e)
        return None


def fetch_and_attach(listing: Listing, query: str, max_results=3):
    """High-level: search Wikimedia, download best image, validate and attach to listing.
    Returns ListingImage or None.
    """
    try:
        hits = search_wikimedia_images(query, max_results=max_results)
        if not hits:
            return None
        pageids = [h.get('pageid') for h in hits if h.get('pageid')]
        pages = get_imageinfo_for_pageids(pageids)
        # iterate pages in order of hits
        for h in hits:
            pid = str(h.get('pageid'))
            page = pages.get(pid)
            if not page:
                continue
            iinfo = page.get('imageinfo')
            if not iinfo:
                continue
            url = iinfo[0].get('url')
            if not url:
                continue
            img_bytes = download_image(url)
            if not img_bytes:
                continue
            if not validate_image_bytes(img_bytes):
                continue
            caption = page.get('title')
            li = save_image_to_listing(listing, img_bytes, filename=None, caption=caption)
            if li:
                return li
        return None
    except Exception as e:
        logger.exception('fetch_and_attach failed for %s: %s', query, e)
        return None
