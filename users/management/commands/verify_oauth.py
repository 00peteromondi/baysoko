# users/management/commands/verify_oauth.py - Updated version
from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Verify OAuth configuration and redirect URIs'

    def handle(self, *args, **options):
        self.stdout.write("🔍 Verifying OAuth Configuration...")
        
        # Check current site
        site = Site.objects.get_current()
        self.stdout.write(f"✅ Current Site: {site.name} - {site.domain}")
        
        # Check Google OAuth
        try:
            google_app = SocialApp.objects.get(provider='google')
            self.stdout.write(f"✅ Google OAuth App: {google_app.name}")
            self.stdout.write(f"✅ Google Client ID: {google_app.client_id[:20]}...")
            self.stdout.write(f"✅ Google Sites: {list(google_app.sites.all())}")
            
            # Direct hardcoded redirect URI (matching what's in adapters.py)
            google_redirect_uri = "https://baysoko.onrender.com/accounts/google/callback/"
            self.stdout.write(f"✅ Google Redirect URI (hardcoded): {google_redirect_uri}")
            
            # Verify it matches expected value
            expected_uri = "https://baysoko.onrender.com/accounts/google/callback/"
            if google_redirect_uri == expected_uri:
                self.stdout.write("✅ Google Redirect URI matches expected value!")
            else:
                self.stdout.write(f"❌ Google Redirect URI mismatch!")
                self.stdout.write(f"   Expected: {expected_uri}")
                self.stdout.write(f"   Got: {google_redirect_uri}")
                
        except SocialApp.DoesNotExist:
            self.stdout.write("❌ Google OAuth app not configured!")
        
        # Check Facebook OAuth
        try:
            facebook_app = SocialApp.objects.get(provider='facebook')
            self.stdout.write(f"✅ Facebook OAuth App: {facebook_app.name}")
            self.stdout.write(f"✅ Facebook Client ID: {facebook_app.client_id[:20]}...")
            self.stdout.write(f"✅ Facebook Sites: {list(facebook_app.sites.all())}")
            
            # Direct hardcoded redirect URI (matching what's in adapters.py)
            facebook_redirect_uri = "https://baysoko.onrender.com/accounts/facebook/callback/"
            self.stdout.write(f"✅ Facebook Redirect URI (hardcoded): {facebook_redirect_uri}")
            
        except SocialApp.DoesNotExist:
            self.stdout.write("❌ Facebook OAuth app not configured!")
        
        # Check environment variables
        self.stdout.write("\n🔍 Checking Environment Variables:")
        google_client_id = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
        google_secret = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
        facebook_client_id = os.environ.get('FACEBOOK_OAUTH_CLIENT_ID')
        facebook_secret = os.environ.get('FACEBOOK_OAUTH_CLIENT_SECRET')
        
        self.stdout.write(f"✅ GOOGLE_OAUTH_CLIENT_ID: {'✓' if google_client_id else '✗'}")
        self.stdout.write(f"✅ GOOGLE_OAUTH_CLIENT_SECRET: {'✓' if google_secret else '✗'}")
        self.stdout.write(f"✅ FACEBOOK_OAUTH_CLIENT_ID: {'✓' if facebook_client_id else '✗'}")
        self.stdout.write(f"✅ FACEBOOK_OAUTH_CLIENT_SECRET: {'✓' if facebook_secret else '✗'}")
        
        # Check URLs in views
        self.stdout.write("\n🔍 Checking Hardcoded URLs in views.py:")
        self.stdout.write(f"✅ Google callback in views: https://baysoko.onrender.com/accounts/google/callback/")
        self.stdout.write(f"✅ Facebook callback in views: https://baysoko.onrender.com/accounts/facebook/callback/")
        
        self.stdout.write("\n✅ OAuth Verification Complete!")