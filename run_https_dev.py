"""
Run the Django WSGI app under a minimal HTTPS dev server using Werkzeug.
Usage:
    python run_https_dev.py

This script will look for `cert.crt` and `cert.key` in the project root.
If Werkzeug (and dependencies) are not installed it prints instructions.

Note: Use only for local development. Don't use in production.
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'baysoko.settings')

try:
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
except Exception as exc:
    print("Could not import Django WSGI application. Make sure you're running from project root and Django is installed.")
    print(str(exc))
    sys.exit(1)

CERT_PATH = os.path.join(os.path.dirname(__file__), 'cert.crt')
KEY_PATH = os.path.join(os.path.dirname(__file__), 'cert.key')
HOST = os.environ.get('DEV_HTTPS_HOST', 'localhost')
PORT = int(os.environ.get('DEV_HTTPS_PORT', '8000'))

try:
    from werkzeug.serving import run_simple
except Exception:
    print("Werkzeug is required to run this script. Install with:")
    print("    pip install werkzeug pyOpenSSL")
    sys.exit(1)

if not (os.path.exists(CERT_PATH) and os.path.exists(KEY_PATH)):
    print(f"No certificate/key pair found at {CERT_PATH} and {KEY_PATH}.")
    print("You can create a self-signed certificate for local development with:")
    print("  openssl req -x509 -newkey rsa:4096 -nodes -out cert.crt -keyout cert.key -days 365 -subj '/CN=localhost'")
    print("Or use the cert.crt and cert.key files already present in the project root if you have them.")
    sys.exit(1)

def main():
    print(f"Starting HTTPS dev server on https://{HOST}:{PORT}/")
    print("Press CTRL+C to stop")

    # If uvicorn is available, prefer running the ASGI application so WebSockets work.
    try:
        import uvicorn
        import sys as _sys
        print("Found uvicorn — starting ASGI server for websocket support")

        # Use the reloader; multiprocessing.freeze_support() will be called
        # in the if __name__ == '__main__' guard to make spawn-based reload
        # safe on Windows.
        should_reload = True

        # Run the project's ASGI application (baysoko.asgi.application)
        uvicorn.run(
            "baysoko.asgi:application",
            host=HOST,
            port=PORT,
            ssl_certfile=CERT_PATH,
            ssl_keyfile=KEY_PATH,
            reload=should_reload,
        )
    except Exception:
        # Fallback to WSGI dev server if uvicorn isn't available
        # run_simple accepts an ssl_context tuple (cert_file, key_file)
        use_reloader = True
        run_simple(HOST, PORT, application, ssl_context=(CERT_PATH, KEY_PATH), use_reloader=use_reloader)


if __name__ == '__main__':
    # On Windows, multiprocessing spawn can require freeze_support for child
    # processes to initialize correctly when using reloaders.
    try:
        import multiprocessing
        multiprocessing.freeze_support()
    except Exception:
        pass

    main()
