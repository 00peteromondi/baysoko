import json
import logging
import os
import re
import time as _time
import random
import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = '''Generate a JSON with the following fields based on the product title:
- category
- description (50-100 words)
- key_features (list of 3–5 short phrases)
- target_audience

Product Title: "{title}"
'''

def _extract_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return None

def _parse_shorthand_listing(text: str):
    """Extract simple structured fields from short freeform listing text."""
    if not text:
        return {}
    t = text
    res = {}
    try:
        m = re.search(r"(?P<currency>kshs|kes|ksh|shs|usd|\$)\s*[:\-]??\s*(?P<price>[0-9,]+(?:\.[0-9]+)?)", t, re.I)
        if not m:
            m = re.search(r"(?P<price>[0-9,]+(?:\.[0-9]+)?)\s*(?P<currency>kshs|kes|ksh|shs|usd)\b", t, re.I)
        if m:
            res['price'] = m.group('price').replace(',', '')
            if m.groupdict().get('currency'):
                res['currency'] = m.group('currency').upper()
        u = re.search(r"per\s+([a-zA-Z0-9\s\.]+)", t, re.I)
        if u:
            res['unit'] = u.group(0).strip()
        q = re.search(r"(?:quantity|qty|stock)\s*[:=]?\s*(?P<qty>\d+)", t, re.I)
        if not q:
            q = re.search(r"\b(?P<qty>\d+)\s*(?:pcs|pieces|units|bags|bags?)\b", t, re.I)
        if q:
            res['quantity'] = q.group('qty')
        loc = re.search(r"location\s*[:\-]?\s*([A-Za-z0-9\s,\-]+)", t, re.I)
        if loc:
            res['location'] = loc.group(1).strip()
        else:
            m2 = re.search(r"\bin\s+([A-Z][a-zA-Z0-9\s]+)", t)
            if m2:
                res['location'] = m2.group(1).strip()
    except Exception:
        pass
    return res

def _enrich_parsed(parsed: dict):
    """Enrich parsed AI output with server-side category mapping and dynamic_fields."""
    try:
        from .models import Category
        cat_name = parsed.get('category')
        if cat_name:
            cat = Category.objects.filter(name__iexact=cat_name.strip()).first()
            if cat:
                parsed['category_id'] = cat.id
                parsed['category_name'] = cat.name
    except Exception:
        logger.debug('Category enrichment failed', exc_info=True)

    try:
        dynamic_keys = ['brand', 'model', 'color', 'material', 'dimensions', 'weight', 'price', 'meta_description']
        dyn = {}
        for k in dynamic_keys:
            if k in parsed and parsed.get(k) is not None:
                dyn[k] = parsed.get(k)
        if dyn:
            parsed['dynamic_fields'] = dyn
    except Exception:
        logger.debug('Failed to construct dynamic_fields', exc_info=True)

    return parsed

def generate_listing_fields(title: str, context=None):
    """Generate structured listing fields using Google Gemini."""
    context_text = ''
    try:
        fail_until = cache.get('gemini_fail_until')
        if fail_until:
            now_ts = timezone.now().timestamp()
            if isinstance(fail_until, (int, float)) and fail_until > now_ts:
                logger.warning('Gemini circuit open until %s; returning fallback', fail_until)
                fallback = {
                    'category': 'Other',
                    'description': f'Auto-generated description for "{title}" is currently unavailable. Please add a description manually.',
                    'key_features': [],
                    'target_audience': 'general',
                }
                return _enrich_parsed(fallback)
    except Exception:
        pass

    if context:
        if isinstance(context, list):
            parts = []
            for m in context:
                if isinstance(m, dict) and 'role' in m and 'content' in m:
                    parts.append(f"{m.get('role')}: {m.get('content')}")
                elif isinstance(m, str):
                    parts.append(str(m))
            context_text = '\n'.join(parts)
        else:
            context_text = str(context)

    prompt = f"Conversation history:\n{context_text}\n\n" + PROMPT_TEMPLATE.format(title=title) if context_text else PROMPT_TEMPLATE.format(title=title)
    shorthand = _parse_shorthand_listing(title if isinstance(title, str) else '')

    model_name = getattr(settings, 'GEMINI_MODEL', None) or os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')
    gemini_env = os.environ.get('GEMINI_API_KEY')
    google_env = os.environ.get('GOOGLE_API_KEY')
    if gemini_env and google_env and gemini_env != google_env:
        logger.info('Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Preferring GEMINI_API_KEY.')
        os.environ['GOOGLE_API_KEY'] = gemini_env
    api_key = gemini_env or google_env or getattr(settings, 'GEMINI_API_KEY', None)
    if api_key:
        os.environ['GEMINI_API_KEY'] = api_key
        os.environ['GOOGLE_API_KEY'] = api_key

    try:
        from google import genai
        client = genai.Client()
        cached = cache.get('gemini_working_model')
        candidates = getattr(settings, 'GEMINI_CANDIDATE_MODELS', None)
        attempt_models = []
        if cached:
            attempt_models.append(cached)
        if candidates:
            if model_name and model_name not in candidates:
                attempt_models.append(model_name)
            for c in candidates:
                if c not in attempt_models:
                    attempt_models.append(c)
        else:
            if model_name:
                attempt_models.append(model_name)

        resp = None
        working_model = None
        probe_attempts = []
        for m in attempt_models:
            try:
                probe_attempts.append({'model': m, 'attempted_at': timezone.now().isoformat()})
                resp = client.models.generate_content(model=m, contents=prompt)
                if resp is not None:
                    working_model = m
                    cache.set('gemini_working_model', working_model, 60*60*24)
                    cache.set('gemini_probe_log', {'attempts': probe_attempts, 'working_model': working_model, 'checked_at': timezone.now().isoformat()}, 60*60*24)
                    break
            except Exception:
                probe_attempts.append({'model': m, 'error': 'attempt failed', 'time': timezone.now().isoformat()})
                continue

        if resp is None:
            cache.set('gemini_probe_log', {'attempts': probe_attempts, 'working_model': None, 'checked_at': timezone.now().isoformat()}, 60*60*24)
            raise RuntimeError('No working Gemini model found via genai client')

        text = getattr(resp, 'text', None) or getattr(resp, 'response', None) or str(resp)
        parsed = _extract_json(text)
        if parsed:
            dyn = parsed.get('dynamic_fields', {}) or {}
            for k, v in shorthand.items():
                if k not in dyn and v is not None:
                    dyn[k] = v
            if dyn:
                parsed['dynamic_fields'] = dyn
            return _enrich_parsed(parsed)
        if shorthand:
            fallback = {
                'category': 'Other',
                'description': f'Auto-generated description for "{title}". Please review.',
                'key_features': [],
                'target_audience': 'general',
                'dynamic_fields': shorthand,
            }
            return _enrich_parsed(fallback)
        return {"raw": text}
    except Exception as e:
        logger.debug('genai client failed; falling back to REST API', exc_info=True)

    # REST fallback
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY not configured for REST fallback')

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {'x-goog-api-key': api_key, 'Content-Type': 'application/json'}
    candidates_rest = getattr(settings, 'GEMINI_CANDIDATE_MODELS', None)
    if candidates_rest:
        models_to_try = [m for m in candidates_rest if m]
        if model_name and model_name in models_to_try:
            models_to_try.remove(model_name)
            models_to_try.insert(0, model_name)
    else:
        models_to_try = [model_name]

    j = None
    for m in models_to_try:
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent'
        max_attempts = 2
        for attempt in range(1, max_attempts+1):
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=30)
                r.raise_for_status()
                j = r.json()
                break
            except RequestException as re:
                status = None
                try:
                    status = re.response.status_code if re.response is not None else None
                except Exception:
                    status = None
                logger.warning('Gemini REST request to model %s attempt %d/%d failed: %s (status=%s)', m, attempt, max_attempts, re, status)
                try:
                    now_ts = timezone.now().timestamp()
                    if status == 429:
                        cache.set('gemini_fail_until', now_ts + 300, timeout=600)
                        break
                    elif status == 503:
                        cache.set('gemini_fail_until', now_ts + 60, timeout=300)
                        break
                    elif status == 404:
                        logger.info('Model %s not found; skipping', m)
                        break
                except Exception:
                    pass
                if attempt == max_attempts:
                    break
                sleep_for = (2 ** attempt) + random.uniform(0, 1)
                _time.sleep(sleep_for)
        if j is not None:
            break

    if j is None:
        try:
            now_ts = timezone.now().timestamp()
            cache.set('gemini_fail_until', now_ts + 120, timeout=300)
            cache.set('gemini_last_error', {'models': models_to_try, 'time': timezone.now().isoformat()}, 60*60*24)
        except Exception:
            pass
        logger.error('Gemini REST generation failed for all models: %s', models_to_try)
        fallback = {
            'category': 'Other',
            'description': f'Auto-generated description for "{title}" is currently unavailable. Please review and complete the fields.',
            'key_features': [],
            'target_audience': 'general',
            'dynamic_fields': shorthand or {},
        }
        return _enrich_parsed(fallback)

    text = None
    try:
        text = j['candidates'][0]['content']['parts'][0]['text']
    except Exception:
        try:
            text = j['candidates'][0]['content'][0]['text']
        except Exception:
            try:
                text = j.get('text') or j.get('response', {}).get('text')
            except Exception:
                text = str(j)
    parsed = _extract_json(text)
    if parsed:
        return _enrich_parsed(parsed)
    return {"raw": text}

def assistant_reply(prompt: str, context=None, user_id=None):
    """
    General Baysoko Assistant reply. Returns a dict with:
        - text: plain text answer
        - platform_items: list of rich objects (listings, stores, orders, subscriptions)
    """
    sys_prompt = (
        "You are the Baysoko Assistant. Help users with buying, selling, creating stores, "
        "listings, editing, deleting, subscriptions, orders, favorites, and general platform tasks. "
        "Answer concisely and provide actionable steps; when appropriate, offer next actions (e.g., 'Add to cart', 'Create listing'). "
        "If the user asks about anything outside the platform, politely redirect to platform‑related topics."
    )
    full_prompt = sys_prompt + "\n\nUser: " + str(prompt)
    platform_items = []

    # 1. Gather user‑specific platform data (if logged in)
    try:
        if user_id is not None:
            from django.contrib.auth import get_user_model
            from listings.models import Listing, Favorite, RecentlyViewed, Cart, Order
            from storefront.models import Store, Subscription
            User = get_user_model()
            user = User.objects.filter(pk=user_id).first()
            platform_lines = []
            fav_limit = getattr(settings, 'ASSISTANT_FAVORITES_LIMIT', 3)
            rec_limit = getattr(settings, 'ASSISTANT_RECENTLY_VIEWED_LIMIT', 3)
            cart_limit = getattr(settings, 'ASSISTANT_CART_LIMIT', 5)
            order_limit = getattr(settings, 'ASSISTANT_RECENT_ORDERS_LIMIT', 2)
            store_limit = getattr(settings, 'ASSISTANT_STORES_LIMIT', 3)
            max_prompt_items = getattr(settings, 'ASSISTANT_PROMPT_MAX_ITEMS', 8)

            if user:
                # Favorites
                favs = Favorite.objects.filter(user=user).select_related('listing')[:fav_limit]
                if favs:
                    platform_lines.append('User favorites:')
                    for f in favs:
                        l = f.listing
                        platform_items.append({
                            'type': 'listing',
                            'id': l.id,
                            'title': l.title,
                            'price': str(l.price),
                            'url': l.get_absolute_url(),
                            'image': l.image.url if l.image else None,
                            'location': l.location,
                            'seller': l.seller.username if l.seller else None,
                        })
                        platform_lines.append(f"- {l.title} | {l.price} | {l.get_absolute_url()}")
                # Cart
                cart = Cart.objects.filter(user=user).first()
                if cart:
                    cart_items = cart.items.select_related('listing')[:cart_limit]
                    if cart_items:
                        platform_lines.append('Cart contents:')
                        for ci in cart_items:
                            l = ci.listing
                            platform_items.append({
                                'type': 'cart_item',
                                'id': l.id,
                                'title': l.title,
                                'price': str(l.price),
                                'url': l.get_absolute_url(),
                                'quantity': ci.quantity,
                                'image': l.image.url if l.image else None,
                            })
                            platform_lines.append(f"- {l.title} x{ci.quantity} | {l.price}")
                # Recent orders
                recent_orders = Order.objects.filter(user=user).order_by('-id')[:order_limit]
                if recent_orders:
                    platform_lines.append('Recent orders:')
                    for o in recent_orders:
                        items = o.order_items.select_related('listing')[:3]
                        item_str = ', '.join([f"{it.listing.title} x{it.quantity}" for it in items])
                        platform_items.append({
                            'type': 'order',
                            'id': o.id,
                            'status': o.status,
                            'total': str(o.total_price),
                            'items_preview': item_str,
                            'url': o.get_absolute_url() if hasattr(o, 'get_absolute_url') else None,
                        })
                        platform_lines.append(f"- Order #{o.id} | {o.status} | {o.total_price} | {item_str}")
                # Recently viewed
                rec = RecentlyViewed.objects.filter(user=user).select_related('listing').order_by('-viewed_at')[:rec_limit]
                if rec:
                    platform_lines.append('Recently viewed:')
                    for r in rec:
                        l = r.listing
                        platform_items.append({
                            'type': 'listing',
                            'id': l.id,
                            'title': l.title,
                            'price': str(l.price),
                            'url': l.get_absolute_url(),
                            'image': l.image.url if l.image else None,
                        })
                        platform_lines.append(f"- {l.title} | {l.price} | {l.get_absolute_url()}")
                # User's stores
                stores = Store.objects.filter(owner=user)[:store_limit]
                if stores:
                    platform_lines.append('Your stores:')
                    for s in stores:
                        platform_items.append({
                            'type': 'store',
                            'id': s.id,
                            'name': s.name,
                            'slug': s.slug,
                            'url': f"/store/{s.slug}/",
                            'image': s.logo.url if s.logo else None,
                        })
                        platform_lines.append(f"- {s.name} | {s.get_absolute_url()}")
            # Global lowest priced item
            lowest = Listing.objects.filter(is_active=True, is_sold=False).order_by('price').first()
            if lowest:
                platform_items.append({
                    'type': 'listing',
                    'id': lowest.id,
                    'title': lowest.title,
                    'price': str(lowest.price),
                    'url': lowest.get_absolute_url(),
                    'image': lowest.image.url if lowest.image else None,
                })
                platform_lines.append('Lowest priced item on platform:')
                platform_lines.append(f"- {lowest.title} | {lowest.price} | {lowest.get_absolute_url()}")
            if platform_lines:
                if len(platform_lines) > max_prompt_items:
                    platform_lines = platform_lines[:max_prompt_items]
                base = sys_prompt + '\nPlatform data (user‑scoped):\n' + '\n'.join(platform_lines) + '\n\n'
                if context and isinstance(context, list):
                    hist = '\n'.join([(h.get('role','user')+': '+h.get('content','')) if isinstance(h, dict) else str(h) for h in context])
                    full_prompt = base + 'Conversation history:\n' + hist + '\n\nUser: ' + str(prompt)
                else:
                    full_prompt = base + 'User: ' + str(prompt)
    except Exception as e:
        logger.debug('Error building platform summary', exc_info=True)

    # 2. Try to answer directly from database (factual queries)
    db_answer = _answer_from_db(prompt, user_id=user_id)
    if db_answer:
        return db_answer

    # 3. Quick intent handling (structured queries)
    low = prompt.strip().lower()
    # Stores
    if re.search(r"\b(store|stores|store info|store details)\b", low):
        try:
            items = _query_stores(prompt=prompt, user_id=user_id)
            text = f"Found {len(items)} store(s)." if items else "No stores found."
            return {'text': text, 'platform_items': items}
        except Exception:
            pass
    # Listings search
    if re.search(r"\b(listings|find listings|show me listings|search listings|find items|show items)\b", low) or re.search(r"\b(find|show)\b.*\blisting|items\b", low):
        try:
            filters = _parse_listing_filters_from_text(prompt)
            items = _query_listings(filters=filters, limit=5, user_id=user_id)
            text = f"Found {len(items)} listing(s) matching your criteria." if items else "No listings found."
            return {'text': text, 'platform_items': items}
        except Exception:
            pass
    # Cheapest item
    if re.search(r"\b(lowest|cheapest|cheapest item|lowest priced|cheapest price)\b", low):
        try:
            item = _get_lowest_priced_listing()
            if item:
                text = f"Lowest priced item: {item.get('title','Unnamed')} — {item.get('price','')}."
                return {'text': text, 'platform_items': [item]}
            else:
                return {'text': 'No active listings found.', 'platform_items': []}
        except Exception:
            pass
    # Store owner lookup
    m_owner = re.search(r"who is the owner of ([\w\s'\-]+)\??", low)
    if m_owner:
        try:
            store_name = m_owner.group(1).strip()
            stores = _query_stores(filters={'name': store_name}, limit=5, user_id=user_id)
            if stores:
                s = stores[0]
                owner = s.get('owner') or 'unknown'
                text = f"{s.get('name')} is owned by {owner}."
                return {'text': text, 'platform_items': [s]}
            else:
                return {'text': f'No store named "{store_name}" found.', 'platform_items': []}
        except Exception:
            pass
    # Subscriptions
    if re.search(r"\b(subscription|subscriptions|subscribe|cancel subscription|renew subscription|my subscription)\b", low):
        try:
            res_text, items = _handle_subscription_intent(prompt, user_id)
            return {'text': res_text, 'platform_items': items}
        except Exception:
            pass
    # Orders
    if re.search(r"\b(order|orders|my orders|track order)\b", low):
        try:
            res_text, items = _handle_order_intent(prompt, user_id)
            if res_text:
                return {'text': res_text, 'platform_items': items}
        except Exception:
            pass

    # 3.5 Try registry-based retrieval (RAG): match patterns, retrieve data, then ask Gemini to generate fluent answer
    try:
        db_result = try_database_query(prompt, user_id)
        if db_result:
            data = db_result.get('data') or []
            # If we have structured data, build augmented prompt and ask Gemini to render a fluent answer
            if data:
                augmented_prompt = (
                    f"The user asked: '{prompt}'.\n"
                    f"Here is the relevant data from our database:\n{db_result.get('context','')}\n\n"
                    "Based on this data, provide a helpful, concise answer. If the data is insufficient, say so."
                )
                try:
                    from google import genai
                    client = genai.Client()
                    model = getattr(settings, 'GEMINI_MODEL', None) or os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')
                    resp = client.models.generate_content(model=model, contents=augmented_prompt)
                    text = getattr(resp, 'text', None) or getattr(resp, 'response', None) or str(resp)
                    return {'text': text or db_result.get('text', ''), 'platform_items': data}
                except Exception:
                    logger.debug('Gemini augmented prompt failed; returning summary', exc_info=True)
                    return {'text': db_result.get('text', ''), 'platform_items': data}
            else:
                # no data found for query (informative message)
                return {'text': db_result.get('text', ''), 'platform_items': []}
    except Exception:
        pass

    # 4. If no quick intent matched, call Gemini for a creative answer
    if context and 'Platform data (user‑scoped):' not in full_prompt:
        try:
            if isinstance(context, list):
                hist = '\n'.join([(h.get('role','user')+': '+h.get('content','')) if isinstance(h, dict) else str(h) for h in context])
                full_prompt = sys_prompt + '\nConversation history:\n' + hist + '\n\nUser: ' + str(prompt)
            else:
                full_prompt = sys_prompt + '\nContext:\n' + str(context) + '\n\nUser: ' + str(prompt)
        except Exception:
            pass

    # Try Gemini client
    try:
        from google import genai
        client = genai.Client()
        model = getattr(settings, 'GEMINI_MODEL', None) or os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')
        resp = client.models.generate_content(model=model, contents=full_prompt)
        text = getattr(resp, 'text', None) or getattr(resp, 'response', None) or str(resp)
        return {'text': text or '', 'platform_items': platform_items}
    except Exception:
        logger.debug('Gemini client failed, falling back to REST', exc_info=True)

    # REST fallback
    try:
        api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY') or getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            return {'text': "Assistant is currently unavailable (API key missing).", 'platform_items': platform_items}
        headers = {'x-goog-api-key': api_key, 'Content-Type': 'application/json'}
        model = getattr(settings, 'GEMINI_MODEL', None) or os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
        payload = {'contents': [{'parts': [{'text': full_prompt}]}]}
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        j = r.json()
        text = j['candidates'][0]['content']['parts'][0]['text']
        return {'text': text, 'platform_items': platform_items}
    except Exception as e:
        logger.exception('assistant_reply REST fallback failed: %s', e)
        return {'text': 'Assistant is temporarily unavailable.', 'platform_items': platform_items}

# ========== QUERY HELPERS ==========
def _query_stores(prompt=None, filters=None, limit=5, user_id=None):
    """Return a list of store dicts with rich fields."""
    try:
        from storefront.models import Store, Subscription
        qs = Store.objects.all()
        if filters:
            name = filters.get('name')
            if name:
                qs = qs.filter(name__icontains=name)
            slug = filters.get('slug')
            if slug:
                qs = qs.filter(slug__iexact=slug)
            owner = filters.get('owner')
            if owner:
                qs = qs.filter(owner__username__icontains=owner)
        if user_id:
            qs = qs.order_by('-owner_id')
        stores = qs[:limit]
        out = []
        for s in stores:
            sub = Subscription.objects.filter(store=s).order_by('-created_at').first()
            status = sub.status if sub else 'none'
            out.append({
                'type': 'store',
                'id': s.id,
                'name': s.name,
                'slug': s.slug,
                'owner': getattr(s.owner, 'username', None),
                'is_premium': getattr(s, 'is_premium', False),
                'subscription_status': status,
                'url': f"/store/{s.slug}/",
                'image': s.logo.url if s.logo else None,
            })
        return out
    except Exception as e:
        logger.debug('_query_stores error: %s', e)
        return []

def _parse_listing_filters_from_text(text: str):
    """Extract simple listing filters from user text."""
    f = {}
    try:
        m = re.search(r"price\s*(?:<=|<|less than)\s*([0-9,\.]+)", text.lower())
        if m:
            f['price_max'] = float(m.group(1).replace(',', ''))
        m = re.search(r"price\s*(?:>=|>|more than|at least)\s*([0-9,\.]+)", text.lower())
        if m:
            f['price_min'] = float(m.group(1).replace(',', ''))
        m = re.search(r"category[:\s]+([a-zA-Z0-9\s\-]+)", text, re.I)
        if m:
            f['category'] = m.group(1).strip()
        m = re.search(r"location[:\s]+([a-zA-Z0-9\s\-]+)", text, re.I)
        if m:
            f['location'] = m.group(1).strip()
        m = re.search(r"keywords?:\s*([\w\s,]+)", text, re.I)
        if m:
            f['q'] = m.group(1).strip()
    except Exception:
        pass
    return f

def _query_listings(filters=None, limit=10, order_by='-date_created', user_id=None):
    """Return a list of listing dicts with rich fields."""
    try:
        from listings.models import Listing, Category
        qs = Listing.objects.filter(is_active=True, is_sold=False)
        if filters:
            if 'price_min' in filters:
                qs = qs.filter(price__gte=filters['price_min'])
            if 'price_max' in filters:
                qs = qs.filter(price__lte=filters['price_max'])
            if 'location' in filters:
                qs = qs.filter(location__icontains=filters['location'])
            if 'category' in filters:
                cat = Category.objects.filter(name__icontains=filters['category']).first()
                if cat:
                    qs = qs.filter(category=cat)
            if 'q' in filters:
                q = filters['q']
                qs = qs.filter(title__icontains=q) | qs.filter(description__icontains=q)
        if order_by:
            qs = qs.order_by(order_by)
        if limit:
            qs = qs[:limit]
        out = []
        for l in qs:
            out.append({
                'type': 'listing',
                'id': l.id,
                'title': l.title,
                'price': str(l.price),
                'url': l.get_absolute_url(),
                'location': getattr(l, 'location', ''),
                'seller': getattr(l.seller, 'username', None),
                'image': l.image.url if l.image else None,
            })
        return out
    except Exception as e:
        logger.debug('_query_listings error: %s', e)
        return []

def _get_lowest_priced_listing(user_id=None, store_id=None):
    """Return a single listing dict for the lowest priced active listing."""
    try:
        from listings.models import Listing
        qs = Listing.objects.filter(is_active=True, is_sold=False)
        if store_id:
            qs = qs.filter(store_id=store_id)
        low = qs.order_by('price').first()
        if not low:
            return None
        return {
            'type': 'listing',
            'id': low.id,
            'title': low.title,
            'price': str(low.price),
            'url': low.get_absolute_url(),
            'location': getattr(low, 'location', ''),
            'seller': getattr(low.seller, 'username', None),
            'image': low.image.url if low.image else None,
        }
    except Exception as e:
        logger.debug('_get_lowest_priced_listing error: %s', e)
        return None

def _answer_from_db(prompt: str, user_id=None):
    """Answer common factual queries directly from the database."""
    try:
        low = (prompt or '').strip().lower()
        # How many stores
        if re.search(r"\bhow many stores\b", low) or re.search(r"\bnumber of stores\b", low):
            from storefront.models import Store
            cnt = Store.objects.count()
            return {'text': f'There are {cnt} store(s) on Baysoko.', 'platform_items': []}
        # How many listings
        if re.search(r"\bhow many listings\b", low) or re.search(r"\bnumber of listings\b", low):
            from listings.models import Listing
            cnt = Listing.objects.filter(is_active=True, is_sold=False).count()
            return {'text': f'There are {cnt} active listing(s) on Baysoko.', 'platform_items': []}
        # Cheapest item
        if re.search(r"\b(cheapest|lowest priced|lowest price|cheapest item)\b", low):
            item = _get_lowest_priced_listing(user_id=user_id)
            if item:
                return {'text': f"Lowest priced item: {item.get('title')} — {item.get('price')}", 'platform_items': [item]}
            return {'text': 'No active listings found.', 'platform_items': []}
        # Order lookup by number
        m = re.search(r"order\s*#?(\d+)", prompt)
        if m:
            try:
                oid = int(m.group(1))
                from listings.models import Order
                o = Order.objects.filter(pk=oid).first()
                if o:
                    items = o.order_items.select_related('listing')[:3]
                    item_str = ', '.join([f"{it.listing.title} x{it.quantity}" for it in items])
                    platform_items = [{
                        'type': 'order',
                        'id': o.id,
                        'status': o.status,
                        'total': str(o.total_price),
                        'items_preview': item_str,
                        'url': o.get_absolute_url() if hasattr(o, 'get_absolute_url') else None,
                    }]
                    return {'text': f'Order #{o.id} — status: {o.status}. Total: {o.total_price}.', 'platform_items': platform_items}
                return None
            except Exception:
                pass
        # Search for listing by name
        m2 = re.search(r"(?:tell me about|show me|what can i get|what is|find)\s+(?:the\s+)?([\w\s'\-]{3,})", prompt, re.I)
        if m2:
            q = m2.group(1).strip()
            if len(q) > 2 and not q.lower().startswith(('how ', 'what ', 'where ', 'who ')):
                from listings.models import Listing
                qs = Listing.objects.filter(title__icontains=q, is_active=True, is_sold=False)[:5]
                items = [{
                    'type': 'listing',
                    'id': l.id,
                    'title': l.title,
                    'price': str(l.price),
                    'url': l.get_absolute_url(),
                    'image': l.image.url if l.image else None,
                } for l in qs]
                if items:
                    return {'text': f'Found {len(items)} listing(s) matching "{q}".', 'platform_items': items}
        # My cart
        if user_id and re.search(r"\b(my cart|what is in my cart|show my cart)\b", low):
            from listings.models import Cart
            cart = Cart.objects.filter(user_id=user_id).first()
            if not cart:
                return {'text': 'Your cart is empty.', 'platform_items': []}
            items = [{
                'type': 'cart_item',
                'id': ci.listing.id,
                'title': ci.listing.title,
                'price': str(ci.listing.price),
                'url': ci.listing.get_absolute_url(),
                'quantity': ci.quantity,
                'image': ci.listing.image.url if ci.listing.image else None,
            } for ci in cart.items.select_related('listing')]
            return {'text': f'You have {len(items)} item(s) in your cart.', 'platform_items': items}
        # My favorites
        if user_id and re.search(r"\b(my favorites|my favourite|show my favorites)\b", low):
            from listings.models import Favorite
            favs = Favorite.objects.filter(user_id=user_id).select_related('listing')[:10]
            items = [{
                'type': 'listing',
                'id': f.listing.id,
                'title': f.listing.title,
                'price': str(f.listing.price),
                'url': f.listing.get_absolute_url(),
                'image': f.listing.image.url if f.listing.image else None,
            } for f in favs]
            return {'text': f'You have {favs.count()} favorite(s).', 'platform_items': items}
        # Stores by owner
        m_owner = re.search(r"stores\s+(?:owned\s+by|by)\s+([\w\s'\-]+)", low)
        if not m_owner:
            m_owner = re.search(r"which\s+stores\s+does\s+([\w\s'\-]+)\s+own", low)
        if m_owner:
            owner_q = m_owner.group(1).strip()
            from django.contrib.auth import get_user_model
            from storefront.models import Store
            User = get_user_model()
            u = User.objects.filter(username__icontains=owner_q).first()
            if u:
                stores = Store.objects.filter(owner=u)
            else:
                stores = Store.objects.filter(name__icontains=owner_q)[:10]
            items = [{
                'type': 'store',
                'id': s.id,
                'name': s.name,
                'slug': s.slug,
                'owner': getattr(s.owner, 'username', None),
                'url': f"/store/{s.slug}/",
                'image': s.logo.url if s.logo else None,
            } for s in stores]
            if items:
                return {'text': f'Found {len(items)} store(s) for "{owner_q}".', 'platform_items': items}
            return {'text': f'No stores found for "{owner_q}".', 'platform_items': []}
        # Category stats
        m_cat = re.search(r"how many (?:listings|items) (?:in|under) category\s+([\w\s'\-]+)", low)
        if not m_cat:
            m_cat = re.search(r"(?:in|under) category\s+([\w\s'\-]+)\b", low)
        if m_cat:
            cat_q = m_cat.group(1).strip()
            from listings.models import Listing, Category
            cat = Category.objects.filter(name__icontains=cat_q).first()
            if cat:
                cnt = Listing.objects.filter(category=cat, is_active=True, is_sold=False).count()
                lowest = Listing.objects.filter(category=cat, is_active=True, is_sold=False).order_by('price').first()
                items = []
                if lowest:
                    items.append({
                        'type': 'listing',
                        'id': lowest.id,
                        'title': lowest.title,
                        'price': str(lowest.price),
                        'url': lowest.get_absolute_url(),
                        'image': lowest.image.url if lowest.image else None,
                    })
                return {'text': f'Category "{cat.name}" has {cnt} active listing(s).', 'platform_items': items}
            else:
                return {'text': f'No category named "{cat_q}" found.', 'platform_items': []}
        # Listings by seller/store
        m_seller = re.search(r"(?:listings|items)\s+(?:by|from)\s+([\w\s'\-]+)", prompt, re.I)
        if not m_seller:
            m_seller = re.search(r"what listings does\s+([\w\s'\-]+)\s+have", prompt, re.I)
        if m_seller:
            seller_q = m_seller.group(1).strip()
            from django.contrib.auth import get_user_model
            from listings.models import Listing
            from storefront.models import Store
            User = get_user_model()
            u = User.objects.filter(username__icontains=seller_q).first()
            if u:
                qs = Listing.objects.filter(seller=u, is_active=True, is_sold=False)[:10]
            else:
                st = Store.objects.filter(name__icontains=seller_q).first()
                if st:
                    qs = Listing.objects.filter(store=st, is_active=True, is_sold=False)[:10]
                else:
                    qs = Listing.objects.filter(title__icontains=seller_q, is_active=True, is_sold=False)[:10]
            items = [{
                'type': 'listing',
                'id': l.id,
                'title': l.title,
                'price': str(l.price),
                'url': l.get_absolute_url(),
                'image': l.image.url if l.image else None,
            } for l in qs]
            if items:
                return {'text': f'Found {len(items)} listing(s) for "{seller_q}".', 'platform_items': items}
            return {'text': f'No listings found for "{seller_q}".', 'platform_items': []}
    except Exception as e:
        logger.debug('_answer_from_db error: %s', e)
    return None


# ========== DATABASE QUERY REGISTRY (Retrieval functions for RAG) ==========
def _get_stores_by_name(name, user_id=None):
    try:
        from storefront.models import Store
        stores = Store.objects.filter(name__icontains=name)[:5]
        items = [{'type': 'store', 'id': s.id, 'name': s.name, 'url': getattr(s, 'get_absolute_url', lambda: f"/store/{s.slug}/")()} for s in stores]
        return {
            'text': f"Found {len(stores)} store(s) matching '{name}'.",
            'data': items,
            'context': '\n'.join([f"- {itm['name']} ({itm['url']})" for itm in items])
        }
    except Exception:
        return {'text': f"Error searching stores for '{name}'.", 'data': [], 'context': ''}


def _get_listings_by_category(category, user_id=None):
    try:
        from listings.models import Listing, Category
        cat = Category.objects.filter(name__icontains=category).first()
        if not cat:
            return {'text': f"No category '{category}' found.", 'data': [], 'context': ''}
        listings = Listing.objects.filter(category=cat, is_active=True, is_sold=False)[:5]
        items = [{'type': 'listing', 'id': l.id, 'title': l.title, 'price': str(getattr(l, 'price', ''))} for l in listings]
        return {
            'text': f"Found {len(listings)} listing(s) in category '{cat.name}'.",
            'data': items,
            'context': '\n'.join([f"- {itm['title']} ({itm['price']})" for itm in items])
        }
    except Exception:
        return {'text': f"Error searching listings for category '{category}'.", 'data': [], 'context': ''}


def _get_orders_for_user(user_id=None):
    try:
        if not user_id:
            return {'text': 'Sign in to view orders.', 'data': [], 'context': ''}
        from listings.models import Order
        orders = Order.objects.filter(user_id=user_id).order_by('-id')[:5]
        items = []
        for o in orders:
            items.append({'type': 'order', 'id': o.id, 'status': o.status, 'total': str(getattr(o, 'total_price', ''))})
        ctx = '\n'.join([f"- Order #{it['id']}: {it['status']} ({it['total']})" for it in items])
        return {'text': f'Found {len(items)} recent order(s).', 'data': items, 'context': ctx}
    except Exception:
        return {'text': 'Error retrieving orders.', 'data': [], 'context': ''}


def _get_cart_contents(user_id=None):
    try:
        if not user_id:
            return {'text': 'Sign in to view your cart.', 'data': [], 'context': ''}
        from listings.models import Cart
        cart = Cart.objects.filter(user_id=user_id).first()
        if not cart or not cart.items.exists():
            return {'text': 'Your cart is empty.', 'data': [], 'context': ''}
        items = []
        for ci in cart.items.select_related('listing'):
            l = ci.listing
            items.append({'type': 'cart', 'id': getattr(l, 'id', None), 'title': l.title, 'price': str(getattr(l, 'price', '')), 'quantity': ci.quantity, 'url': l.get_absolute_url()})
        ctx = '\n'.join([f"- {it['title']} x{it.get('quantity',1)} ({it.get('price')})" for it in items])
        return {'text': f'You have {len(items)} item(s) in your cart.', 'data': items, 'context': ctx}
    except Exception:
        return {'text': 'Error retrieving cart.', 'data': [], 'context': ''}


def _get_user_favorites(user_id=None):
    try:
        if not user_id:
            return {'text': 'Sign in to view favorites.', 'data': [], 'context': ''}
        from listings.models import Favorite
        favs = Favorite.objects.filter(user_id=user_id).select_related('listing')[:10]
        items = []
        for f in favs:
            l = f.listing
            items.append({'type': 'favorite', 'id': getattr(l, 'id', None), 'title': l.title, 'price': str(getattr(l, 'price', '')), 'url': l.get_absolute_url()})
        ctx = '\n'.join([f"- {it['title']} ({it.get('price')})" for it in items])
        return {'text': f'You have {favs.count()} favorite(s).', 'data': items, 'context': ctx}
    except Exception:
        return {'text': 'Error retrieving favorites.', 'data': [], 'context': ''}


def _get_stores_by_owner(owner_name, user_id=None):
    try:
        from django.contrib.auth import get_user_model
        from storefront.models import Store
        User = get_user_model()
        u = User.objects.filter(username__icontains=owner_name).first()
        if u:
            stores = Store.objects.filter(owner=u)[:10]
        else:
            stores = Store.objects.filter(name__icontains=owner_name)[:10]
        items = [{'type': 'store', 'id': s.id, 'name': s.name, 'url': getattr(s, 'get_absolute_url', lambda: f"/store/{s.slug}/")()} for s in stores]
        ctx = '\n'.join([f"- {it['name']} ({it['url']})" for it in items])
        return {'text': f'Found {len(items)} store(s) for "{owner_name}".', 'data': items, 'context': ctx}
    except Exception:
        return {'text': f'Error finding stores for "{owner_name}".', 'data': [], 'context': ''}


def _get_cheapest_in_category(category, user_id=None):
    try:
        from listings.models import Listing, Category
        cat = Category.objects.filter(name__icontains=category).first()
        if not cat:
            return {'text': f"No category '{category}' found.", 'data': [], 'context': ''}
        low = Listing.objects.filter(category=cat, is_active=True, is_sold=False).order_by('price').first()
        if not low:
            return {'text': f'No active listings in category "{cat.name}".', 'data': [], 'context': ''}
        item = {'type': 'listing', 'id': low.id, 'title': low.title, 'price': str(getattr(low, 'price', '')), 'url': low.get_absolute_url()}
        return {'text': f'Cheapest in category "{cat.name}": {low.title} ({getattr(low, "price", "")} )', 'data': [item], 'context': f"- {low.title} ({getattr(low, 'price', '')})"}
    except Exception:
        return {'text': 'Error retrieving cheapest item.', 'data': [], 'context': ''}


def _get_listings_by_seller(seller_name, user_id=None):
    try:
        from django.contrib.auth import get_user_model
        from listings.models import Listing
        from storefront.models import Store
        User = get_user_model()
        u = User.objects.filter(username__icontains=seller_name).first()
        if u:
            qs = Listing.objects.filter(seller=u, is_active=True, is_sold=False)[:10]
        else:
            st = Store.objects.filter(name__icontains=seller_name).first()
            if st:
                qs = Listing.objects.filter(store=st, is_active=True, is_sold=False)[:10]
            else:
                qs = Listing.objects.filter(title__icontains=seller_name, is_active=True, is_sold=False)[:10]
        items = [{'type': 'listing', 'id': l.id, 'title': l.title, 'price': str(getattr(l, 'price', '')), 'url': l.get_absolute_url()} for l in qs]
        ctx = '\n'.join([f"- {it['title']} ({it.get('price')})" for it in items])
        return {'text': f'Found {len(items)} listing(s) for "{seller_name}".', 'data': items, 'context': ctx}
    except Exception:
        return {'text': 'Error retrieving listings for seller.', 'data': [], 'context': ''}


def _get_listing_by_title(title, user_id=None):
    try:
        from listings.models import Listing
        l = Listing.objects.filter(title__icontains=title, is_active=True, is_sold=False).first()
        if not l:
            return {'text': f'No listing found matching "{title}".', 'data': [], 'context': ''}
        item = {'type': 'listing', 'id': l.id, 'title': l.title, 'price': str(getattr(l, 'price', '')), 'url': l.get_absolute_url()}
        return {'text': f'Found listing: {l.title}.', 'data': [item], 'context': f"- {l.title} ({getattr(l, 'price', '')})"}
    except Exception:
        return {'text': 'Error finding listing.', 'data': [], 'context': ''}


def _get_top_sellers(limit=5, user_id=None):
    try:
        from django.contrib.auth import get_user_model
        from django.db.models import Count
        User = get_user_model()
        top = User.objects.annotate(sales=Count('listing__orderitem')).filter(sales__gt=0).order_by('-sales')[:limit]
        items = [{'type': 'user', 'id': u.id, 'name': u.username, 'sales': getattr(u, 'sales', 0)} for u in top]
        ctx = '\n'.join([f"- {it['name']} ({it['sales']} sales)" for it in items])
        return {'text': f'Top {len(items)} sellers by items sold.', 'data': items, 'context': ctx}
    except Exception:
        return {'text': 'Error retrieving top sellers.', 'data': [], 'context': ''}


# Registry: list of pattern/function mappings
QUERY_REGISTRY = [
    {'patterns': [r"\b(store|stores)\b.*\b(name|called)\s+([\w\s]+)"], 'function': _get_stores_by_name, 'extract': lambda m: {'name': m.group(3).strip()}},
    {'patterns': [r"\b(listings|items)\b.*\b(in|under|category)\s+([\w\s]+)"], 'function': _get_listings_by_category, 'extract': lambda m: {'category': m.group(3).strip()}},
    {'patterns': [r"\border(s)?\b|\bmy orders\b"], 'function': _get_orders_for_user, 'extract': lambda m: {}},
    {'patterns': [r"\b(my cart|what is in my cart|show my cart)\b"], 'function': _get_cart_contents, 'extract': lambda m: {}},
    {'patterns': [r"\b(my favorites|my favourite|show my favorites)\b"], 'function': _get_user_favorites, 'extract': lambda m: {}},
    {'patterns': [r"stores\s+(?:owned\s+by|by)\s+([\w\s'\-]+)", r"which\s+stores\s+does\s+([\w\s'\-]+)\s+own"], 'function': _get_stores_by_owner, 'extract': lambda m: {'owner_name': m.group(1).strip()}},
    {'patterns': [r"cheapest\s+in\s+category\s+([\w\s]+)", r"cheapest\s+in\s+([\w\s]+)"], 'function': _get_cheapest_in_category, 'extract': lambda m: {'category': m.group(1).strip()}},
    {'patterns': [r"(listings|items)\s+(?:by|from)\s+([\w\s'\-]+)", r"what listings does\s+([\w\s'\-]+)\s+have"], 'function': _get_listings_by_seller, 'extract': lambda m: {'seller_name': (m.group(2) if m.lastindex and m.lastindex>=2 else m.group(1)).strip()}},
    {'patterns': [r"tell me about\s+([\w\s'\-]{3,})", r"show me\s+([\w\s'\-]{3,})"], 'function': _get_listing_by_title, 'extract': lambda m: {'title': m.group(1).strip()}},
    {'patterns': [r"\b(top|best|leading)\s+sellers?\b", r"\bwho\s+sells\s+the\s+most\b"], 'function': _get_top_sellers, 'extract': lambda m: {}}
]


def try_database_query(prompt: str, user_id=None):
    """Loop through QUERY_REGISTRY and return first matching result dict or None."""
    try:
        low = (prompt or '').strip()
        for entry in QUERY_REGISTRY:
            for pat in entry.get('patterns', []):
                m = re.search(pat, low, re.IGNORECASE)
                if m:
                    params = {}
                    try:
                        params = entry.get('extract', lambda mm: {})(m) or {}
                    except Exception:
                        params = {}
                    params['user_id'] = user_id
                    try:
                        return entry['function'](**params)
                    except Exception:
                        return {'text': 'Error executing query.', 'data': [], 'context': ''}
        return None
    except Exception:
        return None

def _handle_subscription_intent(prompt: str, user_id=None):
    """Handle subscription‑related intents: status, cancel, list plans, renew."""
    try:
        from storefront.subscription_service import SubscriptionService
        from storefront.models import Subscription, Store
        user = None
        if user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(pk=user_id).first()
        low = prompt.strip().lower()
        # Subscription status
        if 'my subscription' in low or 'subscription status' in low or 'what is my subscription' in low:
            if not user:
                return ('Please sign in to view your subscriptions.', [])
            summary = SubscriptionService.get_subscription_summary(user)
            text = f"You have {summary.get('total_stores',0)} store(s). Active subscriptions: {summary.get('active_subscriptions',0)}."
            # Optionally return subscription items
            items = []
            active_subs = Subscription.objects.filter(store__owner=user, status='active')[:3]
            for sub in active_subs:
                items.append({
                    'type': 'subscription',
                    'store_name': sub.store.name,
                    'plan': sub.plan_name,
                    'status': sub.status,
                    'expires': sub.current_period_end.isoformat() if sub.current_period_end else None,
                })
            return (text, items)
        # Cancel subscription
        if 'cancel subscription' in low or 'cancel my subscription' in low:
            if not user:
                return ('Please sign in to cancel subscriptions.', [])
            sub = Subscription.objects.filter(store__owner=user).order_by('-created_at').first()
            if not sub:
                return ('No subscription found to cancel.', [])
            success = SubscriptionService.cancel_subscription(sub, cancel_at_period_end=False)
            return ('Subscription canceled.' if success else 'Failed to cancel subscription.', [])
        # List plans
        if 'list plans' in low or 'plans' == low.strip() or 'what plans' in low:
            plans = SubscriptionService.get_display_plans()
            text = 'Available plans: ' + ', '.join([f"{k} ({v['price']})" for k,v in plans.items()])
            return (text, [])
        # Default summary
        if user:
            summ = SubscriptionService.get_subscription_summary(user)
            text = f"Subscription summary: {summ.get('total_stores',0)} stores; {summ.get('active_subscriptions',0)} active subscriptions."
            return (text, [])
        return ('Subscription help: you can ask about your subscription status, cancel a subscription, or list available plans.', [])
    except Exception as e:
        logger.debug('_handle_subscription_intent error: %s', e)
        return ('Subscription service unavailable.', [])

def _handle_order_intent(prompt: str, user_id=None):
    """Handle order‑related intents: track, list recent orders."""
    try:
        from listings.models import Order
        low = prompt.strip().lower()
        # Track order by number
        m = re.search(r"track\s+order\s*#?(\d+)", low)
        if m:
            oid = int(m.group(1))
            if user_id:
                o = Order.objects.filter(pk=oid, user_id=user_id).first()
            else:
                o = Order.objects.filter(pk=oid).first()
            if o:
                items = o.order_items.select_related('listing')[:3]
                item_str = ', '.join([f"{it.listing.title} x{it.quantity}" for it in items])
                platform_items = [{
                    'type': 'order',
                    'id': o.id,
                    'status': o.status,
                    'total': str(o.total_price),
                    'items_preview': item_str,
                    'url': o.get_absolute_url() if hasattr(o, 'get_absolute_url') else None,
                }]
                return (f'Order #{o.id} — status: {o.status}. Total: {o.total_price}.', platform_items)
            else:
                return (f'Order #{oid} not found.', [])
        # List recent orders
        if re.search(r"\b(my orders|recent orders)\b", low):
            if not user_id:
                return ('Please sign in to view your orders.', [])
            orders = Order.objects.filter(user_id=user_id).order_by('-id')[:5]
            items = []
            for o in orders:
                items_preview = ', '.join([f"{it.listing.title} x{it.quantity}" for it in o.order_items.select_related('listing')[:3]])
                items.append({
                    'type': 'order',
                    'id': o.id,
                    'status': o.status,
                    'total': str(o.total_price),
                    'items_preview': items_preview,
                    'url': o.get_absolute_url() if hasattr(o, 'get_absolute_url') else None,
                })
            text = f'You have {len(orders)} recent order(s).' if orders else 'No orders found.'
            return (text, items)
    except Exception as e:
        logger.debug('_handle_order_intent error: %s', e)
    return (None, [])