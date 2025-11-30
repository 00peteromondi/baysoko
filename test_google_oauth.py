import os
import django
import sys

sys.path.append('/opt/render/project/src')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'homabay_souq.settings')
django.setup()

from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site

def test_config():
    print("🧪 Testing Google OAuth Configuration")
    print("=" * 50)
    
    # Check environment variables
    client_id = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
    secret = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
    
    print(f"Environment GOOGLE_OAUTH_CLIENT_ID: {'✅' if client_id else '❌'}")
    print(f"Environment GOOGLE_OAUTH_CLIENT_SECRET: {'✅' if secret else '❌'}")
    
    if client_id:
        print(f"Client ID starts with: {client_id[:20]}...")
    if secret:
        print(f"Secret starts with: {secret[:10]}...")
    
    # Check database
    try:
        site = Site.objects.get_current()
        print(f"Current site: {site.domain} (ID: {site.id})")
        
        google_apps = SocialApp.objects.filter(provider='google', sites=site)
        print(f"Google SocialApps in DB: {google_apps.count()}")
        
        for app in google_apps:
            print(f"  - Name: {app.name}")
            print(f"    Client ID: {app.client_id[:20]}...")
            print(f"    Secret: {app.secret[:10]}...")
            print(f"    Sites: {[s.domain for s in app.sites.all()]}")
            
    except Exception as e:
        print(f"❌ Error checking database: {e}")

if __name__ == "__main__":
    test_config()