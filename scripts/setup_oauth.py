# scripts/setup_oauth.py
#!/usr/bin/env python
import os
import django
import sys

# Add the project to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'baysoko.settings')
django.setup()

from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp

def setup_oauth():
    print("🚀 Setting up OAuth for production...")
    
    # Get or create the site
    site, created = Site.objects.get_or_create(
        id=1,
        defaults={
            'domain': 'bay-soko.onrender.com',
            'name': 'Baysoko Marketplace'
        }
    )
    
    if created:
        print(f"✅ Created new site: {site.name}")
    else:
        site.domain = 'bay-soko.onrender.com'
        site.name = 'Baysoko Marketplace'
        site.save()
        print(f"✅ Updated site: {site.name}")
    
    # Set up Google OAuth
    google_client_id = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
    google_secret = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
    
    if google_client_id and google_secret:
        google_app, created = SocialApp.objects.get_or_create(
            provider='google',
            defaults={
                'name': 'Google',
                'client_id': google_client_id,
                'secret': google_secret,
            }
        )
        
        if not created:
            google_app.client_id = google_client_id
            google_app.secret = google_secret
            google_app.save()
        
        google_app.sites.add(site)
        print(f"✅ Google OAuth app {'created' if created else 'updated'}")
    else:
        print("❌ Google OAuth credentials not found in environment")
    
    # Set up Facebook OAuth
    facebook_client_id = os.environ.get('FACEBOOK_OAUTH_CLIENT_ID')
    facebook_secret = os.environ.get('FACEBOOK_OAUTH_CLIENT_SECRET')
    
    if facebook_client_id and facebook_secret:
        facebook_app, created = SocialApp.objects.get_or_create(
            provider='facebook',
            defaults={
                'name': 'Facebook',
                'client_id': facebook_client_id,
                'secret': facebook_secret,
            }
        )
        
        if not created:
            facebook_app.client_id = facebook_client_id
            facebook_app.secret = facebook_secret
            facebook_app.save()
        
        facebook_app.sites.add(site)
        print(f"✅ Facebook OAuth app {'created' if created else 'updated'}")
    else:
        print("❌ Facebook OAuth credentials not found in environment")
    
    print("\n✅ OAuth setup complete!")
    print(f"🌐 Site Domain: {site.domain}")
    print(f"🔗 Google Callback: https://bay-soko.onrender.com/accounts/google/callback/")
    print(f"🔗 Facebook Callback: https://bay-soko.onrender.com/accounts/facebook/callback/")

if __name__ == '__main__':
    setup_oauth()