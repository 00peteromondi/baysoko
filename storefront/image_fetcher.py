import logging
import requests
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.text import slugify
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from listings.models import Listing, ListingImage

logger = logging.getLogger(__name__)

# Wikimedia Commons API endpoints
WIKIMEDIA_API = 'https://commons.wikimedia.org/w/api.php'
WIKIMEDIA_HEADERS = {
    'User-Agent': 'BaysokoBulkImporter/1.0 (https://baysoko.com; bulk image import)'
}
ALLOWED_IMAGE_MIME_PREFIX = 'image/'
GENERATED_IMAGE_SIZE = (1200, 900)


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
        r = requests.get(WIKIMEDIA_API, params=params, headers=WIKIMEDIA_HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        hits = data.get('query', {}).get('search', [])
        return hits
    except Exception as e:
        logger.warning('Wikimedia search failed for %s: %s', query, e)
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
        r = requests.get(WIKIMEDIA_API, params=params, headers=WIKIMEDIA_HEADERS, timeout=10)
        r.raise_for_status()
        return r.json().get('query', {}).get('pages', {})
    except Exception as e:
        logger.warning('Wikimedia imageinfo fetch failed: %s', e)
        return {}


def download_image(url, max_bytes=5 * 1024 * 1024):
    """Download image bytes with a size limit."""
    try:
        r = requests.get(url, stream=True, headers=WIKIMEDIA_HEADERS, timeout=15)
        r.raise_for_status()
        content_type = (r.headers.get('Content-Type') or '').split(';', 1)[0].strip().lower()
        if content_type and not content_type.startswith(ALLOWED_IMAGE_MIME_PREFIX):
            logger.debug('Skipping non-image URL %s with content type %s', url, content_type)
            return None
        content_length = r.headers.get('Content-Length')
        if content_length:
            try:
                if int(content_length) > max_bytes:
                    logger.debug('Skipping oversized image %s (%s bytes)', url, content_length)
                    return None
            except (TypeError, ValueError):
                pass
        content = BytesIO()
        total = 0
        for chunk in r.iter_content(8192):
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                logger.debug('Skipping oversized image %s after reading %s bytes', url, total)
                return None
            content.write(chunk)
        return content.getvalue()
    except Exception as e:
        logger.warning('Failed to download image %s: %s', url, e)
        return None


def validate_image_bytes(img_bytes):
    try:
        im = Image.open(BytesIO(img_bytes))
        im.verify()
        return True
    except (UnidentifiedImageError, Exception) as e:
        logger.debug('Invalid image bytes: %s', e)
        return False


def save_image_to_listing(listing: Listing, img_bytes: bytes, filename=None, caption=None):
    try:
        if not filename:
            filename = slugify(listing.title)[:50] or 'listing'
            filename = f"{filename}.jpg"

        content_file = ContentFile(img_bytes)
        li = ListingImage(listing=listing)
        # Some Cloudinary versions return None for an empty field proxy before
        # assignment. In that case, save through Django storage and assign the
        # returned string name/public id so the DB never receives a ContentFile.
        image_field = getattr(li, 'image', None)
        if hasattr(image_field, 'save'):
            image_field.save(filename, content_file, save=False)
        else:
            upload_to = 'listing_images/gallery/'
            try:
                model_field = ListingImage._meta.get_field('image')
                upload_to = getattr(model_field, 'upload_to', upload_to) or upload_to
            except Exception:
                pass
            saved_name = default_storage.save(f'{upload_to}{filename}', content_file)
            li.image = saved_name
        if caption:
            li.caption = caption
        li.save()
        return li
    except Exception as e:
        logger.exception('Failed saving image to listing %s: %s', listing.id, e)
        return None


def _load_font(size):
    for path in (
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf',
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap_text(draw, text, font, max_width, max_lines=4):
    words = str(text or '').split()
    if not words:
        return []

    lines = []
    current = ''
    for word in words:
        candidate = f'{current} {word}'.strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) >= max_lines - 1:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines


def generate_title_image_bytes(title, subtitle='Baysoko Marketplace'):
    """Generate a simple title-matched JPEG fallback image."""
    title = str(title or 'Baysoko Product').strip() or 'Baysoko Product'
    seed = sum(ord(ch) for ch in title)
    palettes = [
        ((23, 92, 78), (244, 185, 66)),
        ((37, 64, 143), (229, 85, 54)),
        ((83, 42, 114), (67, 176, 123)),
        ((116, 62, 35), (73, 143, 184)),
        ((32, 96, 111), (213, 92, 121)),
    ]
    bg, accent = palettes[seed % len(palettes)]
    width, height = GENERATED_IMAGE_SIZE
    image = Image.new('RGB', GENERATED_IMAGE_SIZE, bg)
    draw = ImageDraw.Draw(image)

    for y in range(height):
        blend = y / height
        color = tuple(int(bg[i] * (1 - blend) + max(bg[i] - 42, 0) * blend) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)

    draw.rectangle([0, height - 190, width, height], fill=accent)
    draw.ellipse([width - 330, -120, width + 130, 340], fill=tuple(min(c + 28, 255) for c in bg))
    draw.ellipse([-160, height - 280, 280, height + 160], fill=tuple(max(c - 28, 0) for c in bg))

    title_font = _load_font(74)
    subtitle_font = _load_font(30)
    lines = _wrap_text(draw, title, title_font, width - 180, max_lines=4)
    line_height = 92
    title_block_height = max(len(lines), 1) * line_height
    y = max(120, (height - 190 - title_block_height) // 2)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        x = (width - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=title_font, fill=(255, 255, 255))
        y += line_height

    subtitle_text = str(subtitle or 'Baysoko Marketplace')
    bbox = draw.textbbox((0, 0), subtitle_text, font=subtitle_font)
    draw.text(((width - (bbox[2] - bbox[0])) // 2, height - 118), subtitle_text, font=subtitle_font, fill=(255, 255, 255))

    output = BytesIO()
    image.save(output, format='JPEG', quality=88, optimize=True)
    return output.getvalue()


def attach_generated_title_image(listing: Listing, title=None, subtitle=None):
    image_bytes = generate_title_image_bytes(title or listing.title, subtitle=subtitle or 'Baysoko Marketplace')
    filename = f"{slugify(title or listing.title)[:50] or f'listing-{listing.pk}'}-generated.jpg"
    return save_image_to_listing(
        listing,
        image_bytes,
        filename=filename,
        caption=f'Generated image for {title or listing.title}',
    )


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
            mime = (iinfo[0].get('mime') or '').lower()
            if mime and not mime.startswith(ALLOWED_IMAGE_MIME_PREFIX):
                logger.debug('Skipping Wikimedia result %s with mime %s', page.get('title'), mime)
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
