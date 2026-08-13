import os
import django
import sys

# Setup Django
sys.path.append('/opt/render/project/src')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'baysoko.settings')
django.setup()

from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp

def reset_google_completely():
    print("🔄 COMPLETELY Resetting Google OAuth Configuration...")
    print("=" * 60)
    
    # Get the site
    site = Site.objects.get_current()
    print(f"🌐 Using site: {site.domain}")
    
    # Get credentials from environment
    client_id = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
    secret = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
    
    print(f"🔑 Client ID from env: {'✅' if client_id else '❌'}")
    print(f"🔒 Secret from env: {'✅' if secret else '❌'}")
    
    if client_id:
        print(f"   Client ID: {client_id}")
    if secret:
        print(f"   Secret: {secret[:10]}...")
    
    if not client_id or not secret:
        print("❌ ERROR: Missing Google OAuth credentials in environment variables")
        print("   Please set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET")
        return False
    
    # Delete ALL existing Google apps
    deleted_count, _ = SocialApp.objects.filter(provider='google').delete()
    print(f"🗑️  Deleted {deleted_count} existing Google SocialApp(s)")
    
    # Create new Google app
    try:
        google_app = SocialApp.objects.create(
            provider='google',
            name='Google',
            client_id=client_id,
            secret=secret,
        )
        google_app.sites.add(site)
        
        print("✅ SUCCESS: Created new Google SocialApp")
        print(f"🔑 Client ID: {google_app.client_id}")
        print(f"🌐 Site: {site.domain}")
        
        # Verify the app was saved
        saved_apps = SocialApp.objects.filter(provider='google')
        print(f"📊 Total Google apps in DB: {saved_apps.count()}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR creating SocialApp: {e}")
        return False

if __name__ == "__main__":
    success = reset_google_completely()
    if success:
        print("\n🎉 Google OAuth reset completed successfully!")
        print("   You can now test Google login.")
    else:
        print("\n💥 Google OAuth reset failed!")
        print("   Check your environment variables and try again.")