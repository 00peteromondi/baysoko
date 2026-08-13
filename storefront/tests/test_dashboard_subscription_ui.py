from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

from ..models import Store, Subscription
from ..subscription_service import SubscriptionService

User = get_user_model()


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class DashboardSubscriptionUITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='dashuser', email='dash@test.com', password='pass')
        self.store = Store.objects.create(owner=self.user, name='DashStore', slug='dashstore')
        self.client.login(username='dashuser', password='pass')

    def test_dashboard_allows_create_when_trial_active(self):
        # Start a trial so the dashboard should allow creating stores/listings
        success, result = SubscriptionService.start_trial_with_tracking(self.store, 'premium', '0712345678', self.user)
        self.assertTrue(success)
        url = reverse('storefront:seller_dashboard')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # When trial is active the direct create links should be present
        self.assertIn(reverse('storefront:store_create'), content)
        self.assertIn(reverse('listing-create'), content)

    def test_dashboard_allows_create_when_active_subscription(self):
        # Create an active subscription for the store
        now = timezone.now()
        sub = Subscription.objects.create(
            store=self.store,
            plan='premium',
            status='active',
            amount=1000,
            started_at=now,
            current_period_end=now + timedelta(days=30),
        )
        # ensure store premium flag consistent
        self.store.is_premium = True
        self.store.save()

        url = reverse('storefront:seller_dashboard')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn(reverse('storefront:store_create'), content)
        self.assertIn(reverse('listing-create'), content)

    def test_dashboard_allows_features_when_trial_active(self):
        # Start a trial so the dashboard should allow analytics, inventory, bulk
        success, result = SubscriptionService.start_trial_with_tracking(self.store, 'enterprise', '0712345678', self.user)
        self.assertTrue(success)
        url = reverse('storefront:seller_dashboard')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # Analytics link
        self.assertIn(reverse('storefront:seller_analytics'), content)
        # Inventory and bulk require store slug
        self.assertIn(reverse('storefront:inventory_dashboard', kwargs={'slug': self.store.slug}), content)
        self.assertIn(reverse('storefront:bulk_import_data', kwargs={'slug': self.store.slug}), content)

    def test_dashboard_allows_features_when_active_subscription(self):
        # Create an active subscription for the store
        now = timezone.now()
        sub = Subscription.objects.create(
            store=self.store,
            plan='enterprise',
            status='active',
            amount=2000,
            started_at=now,
            current_period_end=now + timedelta(days=30),
        )
        # ensure store premium flag consistent
        self.store.is_premium = True
        self.store.save()

        url = reverse('storefront:seller_dashboard')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn(reverse('storefront:seller_analytics'), content)
        self.assertIn(reverse('storefront:inventory_dashboard', kwargs={'slug': self.store.slug}), content)
        self.assertIn(reverse('storefront:bulk_import_data', kwargs={'slug': self.store.slug}), content)
