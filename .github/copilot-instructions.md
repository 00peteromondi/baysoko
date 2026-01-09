Purpose
-------
Short, actionable guidance for AI coding agents to be productive in this repository.

Quick start (local)
- **Install:** `python -m venv .venv && .venv\Scripts\pip install -r requirements.txt`
- **DB / migrations:** `python manage.py migrate`
- **Run dev server (HTTP):** `python manage.py runserver`
- **Run dev server (HTTPS helper):** `python run_https_dev.py`
- **Run Celery worker:** `celery -A celery_app worker -l info`
- **Run Celery beat (schedules):** `celery -A celery_app beat -l info`
- **Run tests:** `python manage.py test`

Architecture & key patterns
- This is a Django monolith with a few integration boundaries you should know:
  - HTTP/Django app: entrypoint is [manage.py](manage.py).
  - ASGI / WebSockets: [homabay_souq/asgi.py](homabay_souq/asgi.py) + Channels. Websocket routes live in [delivery/routing.py](delivery/routing.py) and consumers in [delivery/consumers.py](delivery/consumers.py). Groups follow `order_<id>` and `user_<id>` naming.
  - Background work: Celery configuration is in [celery_app.py](celery_app.py). Tasks are auto-discovered under `delivery.integration` and `delivery.tasks` falls back to a sync function if Celery is unavailable (see [delivery/tasks.py](delivery/tasks.py)).
  - Webhooks/outgoing integration: `listings/webhook_service.py` builds signed HMAC payloads and sends to `ECOMMERCE_WEBHOOK_URL` / `DELIVERY_SYSTEM_URL`. Look for headers `X-Webhook-Signature` and `X-Event-Type`.
  - Media storage: Cloudinary is optional and configured in [homabay_souq/settings.py](homabay_souq/settings.py). If not configured, local `MEDIA_ROOT` is used.

Environment & deployment cues
- Uses `python-decouple` to read `.env`/env vars. Key env vars: `SECRET_KEY`, `DATABASE_URL` (Postgres on production), `CLOUDINARY_*`, `DELIVERY_WEBHOOK_SECRET`, `GOOGLE_OAUTH_CLIENT_ID/SECRET`.
- If `DATABASE_URL` is present the project assumes production Postgres; otherwise it runs with `db.sqlite3` (dev).
- Channels layer uses an in-memory backend in settings (development). WebSocket behavior across multiple processes is not persisted unless channel layer is replaced in production.

Repository conventions (important for automated edits)
- App-local modules: each Django app exposes `models.py`, `views.py`, `tasks.py` or `integration.py` for external/sync code.
- Background tasks: prefer registering tasks in `delivery.integration.tasks` so Celery autodiscovery picks them up. Where present, modules often provide a synchronous fallback (see [delivery/tasks.py](delivery/tasks.py)).
- Webhook signing/verification: use deterministic JSON serialization (`sort_keys=True`) and HMAC-SHA256 signing. See [listings/webhook_service.py](listings/webhook_service.py) for the canonical implementation.
- WebSocket message contract: `order_status_update` events send `{ 'type': ..., 'status': ..., 'payload': {...} }`.

Where to change behavior
- To add a periodic job, update `app.conf.beat_schedule` in [celery_app.py](celery_app.py).
- To add new webhook consumers or endpoints, follow `listings/webhook_service.py`'s payload structure and header verification.
- To modify file storage behavior, update Cloudinary settings in [homabay_souq/settings.py](homabay_souq/settings.py).

Tests and debugging tips
- Tests run via `python manage.py test`. When debugging API/webhook flows, enable `DEBUG` and run the dev server.
- For WebSocket testing, connect to `ws/orders/<order_id>/` or `ws/users/<user_id>/` and listen for `order.status` and `user.order.status` messages.

If you edit code, keep changes minimal and local to the app unless cross-cutting behavior (settings, middleware, Celery) must change. When in doubt, run `python manage.py test` before committing.

Files to inspect first when onboarding
- [manage.py](manage.py) — Django entrypoint
- [homabay_souq/settings.py](homabay_souq/settings.py) — environment flags, Cloudinary, Channels
- [celery_app.py](celery_app.py) — Celery/beat config
- [delivery/consumers.py](delivery/consumers.py), [delivery/routing.py](delivery/routing.py) — WebSocket contracts
- [listings/webhook_service.py](listings/webhook_service.py) — outgoing webhook format/signing

Questions for maintainers
- Should we standardize on a single channel layer for local testing (Redis) to allow multi-process WebSocket tests?  
- Is there a preferred command for running Celery in dev (docker-compose vs local Celery)?

Feedback
--------
If any of the above is inaccurate or you want additional examples (common PR patterns, lint/test commands, or CI hooks), tell me what to expand.
