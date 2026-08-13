from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
from ..models import Store, Subscription, MpesaPayment
from ..subscription_service import SubscriptionService


User = get_user_model()


class SubscriptionStateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', email='t@test.com', password='pass')
        self.store = Store.objects.create(owner=self.user, name='TStore', slug='tstore')

    def test_subscribe_immediately_creates_unpaid_and_no_premium(self):
        success, sub = SubscriptionService.subscribe_immediately(self.store, 'basic', '0712345678')
        self.assertTrue(success)
        self.assertEqual(sub.status, 'unpaid')
        self.store.refresh_from_db()
        self.assertFalse(self.store.is_premium, "Store should not be premium until payment activates subscription")

    def test_activate_subscription_safely_with_completed_payment(self):
        # Create unpaid subscription
        _, sub = SubscriptionService.subscribe_immediately(self.store, 'basic', '0712345678')
        # Create a successful payment that matches the subscription
        payment = MpesaPayment.objects.create(
            subscription=sub,
            checkout_request_id='CR123',
            merchant_request_id='MR123',
            phone_number='+254712345678',
            amount=sub.amount,
            status='completed'
        )

        ok, msg = SubscriptionService.activate_subscription_safely(sub, payment=payment)
        self.assertTrue(ok, msg)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'active')
        self.store.refresh_from_db()
        self.assertTrue(self.store.is_premium)

    def test_failed_payment_does_not_activate_and_store_not_premium(self):
        _, sub = SubscriptionService.subscribe_immediately(self.store, 'basic', '0712345678')
        # Create a failed payment
        payment = MpesaPayment.objects.create(
            subscription=sub,
            checkout_request_id='CR999',
            merchant_request_id='MR999',
            phone_number='+254700000000',
            amount=sub.amount,
            status='failed'
        )

        ok, msg = SubscriptionService.activate_subscription_safely(sub, payment=payment)
        self.assertFalse(ok)
        sub.refresh_from_db()
        self.assertNotEqual(sub.status, 'active')
        self.store.refresh_from_db()
        self.assertFalse(self.store.is_premium)

    def test_trial_conversion_payment_failure_keeps_trial_active(self):
        # Start trial
        success, result = SubscriptionService.start_trial_with_tracking(self.store, 'enterprise', '0712345678', self.user)
        self.assertTrue(success)
        sub = result['subscription'] if isinstance(result, dict) else result

        # Patch process_payment to simulate failure
        from unittest.mock import patch
        with patch.object(SubscriptionService, 'process_payment', return_value=(False, 'simulated failure')):
            ok, msg = SubscriptionService.convert_trial_to_paid(sub, phone_number=sub.mpesa_phone)
            self.assertFalse(ok)
            # Trial should still be active
            sub.refresh_from_db()
            self.assertEqual(sub.status, 'trialing')
            self.store.refresh_from_db()
            self.assertTrue(self.store.is_premium)
