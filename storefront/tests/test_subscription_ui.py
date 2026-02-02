from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from .test_subscription_states import User, SubscriptionStateTests
from ..models import Store, Subscription
from ..subscription_service import SubscriptionService

User = get_user_model()


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class SubscriptionUITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='uiuser', email='ui@test.com', password='pass')
        self.store = Store.objects.create(owner=self.user, name='UIStore', slug='uistore')
        self.client.login(username='uiuser', password='pass')

    def test_subscription_manage_shows_plan_and_trial_days(self):
        # Start a trial with 7 days default, then adjust to 3 days remaining
        success, result = SubscriptionService.start_trial_with_tracking(self.store, 'premium', '0712345678', self.user)
        self.assertTrue(success)
        sub = result['subscription'] if isinstance(result, dict) else result
        sub.trial_ends_at = timezone.now() + timedelta(days=3, minutes=1)
        sub.save()
        url = reverse('storefront:subscription_manage', kwargs={'slug': self.store.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('trial_days_remaining', resp.context)
        self.assertEqual(resp.context['trial_days_remaining'], 3)
        self.assertIn('trial_status_message', resp.context)
        self.assertIn('remaining', resp.context['trial_status_message'])

    def test_trial_expiry_locks_features_and_manage_displays_ended(self):
        # Start a trial then expire it
        success, result = SubscriptionService.start_trial_with_tracking(self.store, 'premium', '0712345678', self.user)
        self.assertTrue(success)
        sub = result['subscription'] if isinstance(result, dict) else result
        sub.trial_ends_at = timezone.now() - timedelta(days=1)
        sub.save()
        # Enforce expiry
        SubscriptionService.enforce_trial_expiry()
        self.store.refresh_from_db()
        self.assertFalse(self.store.is_premium)

        url = reverse('storefront:subscription_manage', kwargs={'slug': self.store.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context.get('trial_status_message'), 'Trial period ended')

    def test_failed_payment_does_not_remove_access_if_trial_active(self):
        # Start an active trial via service so store premium is enabled
        success, result = SubscriptionService.start_trial_with_tracking(self.store, 'enterprise', '0712345678', self.user)
        self.assertTrue(success)
        sub = result['subscription'] if isinstance(result, dict) else result
        # Simulate failed payment attempt converting trial by mocking process_payment
        from unittest.mock import patch
        with patch.object(SubscriptionService, 'process_payment', return_value=(False, 'simulated failure')):
            ok, msg = SubscriptionService.convert_trial_to_paid(sub, phone_number=sub.mpesa_phone or '+254700000000')
            self.assertFalse(ok)

        # Trial should still be active and store remains premium
        sub.refresh_from_db()
        self.store.refresh_from_db()
        self.assertEqual(sub.status, 'trialing')
        self.assertTrue(self.store.is_premium)
