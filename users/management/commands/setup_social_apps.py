from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Setup social applications for OAuth providers'

    def handle(self, *args, **options):
        # Get or create the current site
        site, created = Site.objects.get_or_create(
            id=settings.SITE_ID,
            defaults={
                'domain': 'homabaysouq.onrender.com',
                'name': 'HomaBay Souq'
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created site: {site.domain}'))
        else:
            # Update the site domain if it's still example.com
            if site.domain in ['example.com', 'localhost:8000', 'homabaysouq.onrender.com']:
                site.domain = 'homabaysouq.onrender.com'
                site.name = 'HomaBay Souq'
                site.save()
                self.stdout.write(self.style.SUCCESS(f'Updated site to: {site.domain}'))

        # Google SocialApp
        google_client_id = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
        google_secret = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
        
        if google_client_id and google_secret:
            google_app, created = SocialApp.objects.update_or_create(
                provider='google',
                defaults={
                    'name': 'Google',
                    'client_id': google_client_id,
                    'secret': google_secret,
                }
            )
            google_app.sites.add(site)
            if created:
                self.stdout.write(self.style.SUCCESS('✅ Google SocialApp created successfully'))
            else:
                self.stdout.write(self.style.SUCCESS('✅ Google SocialApp updated successfully'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Google OAuth credentials not found in environment variables'))

        # Facebook SocialApp
        facebook_client_id = os.environ.get('FACEBOOK_OAUTH_CLIENT_ID')
        facebook_secret = os.environ.get('FACEBOOK_OAUTH_CLIENT_SECRET')
        
        if facebook_client_id and facebook_secret:
            facebook_app, created = SocialApp.objects.update_or_create(
                provider='facebook',
                defaults={
                    'name': 'Facebook',
                    'client_id': facebook_client_id,
                    'secret': facebook_secret,
                }
            )
            facebook_app.sites.add(site)
            if created:
                self.stdout.write(self.style.SUCCESS('✅ Facebook SocialApp created successfully'))
            else:
                self.stdout.write(self.style.SUCCESS('✅ Facebook SocialApp updated successfully'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Facebook OAuth credentials not found in environment variables'))

        self.stdout.write(self.style.SUCCESS('🎉 Social app setup completed!'))