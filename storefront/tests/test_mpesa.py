from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock
from ..models import Store, Subscription, MpesaPayment
from datetime import datetime, timedelta
import json

User = get_user_model()

class MpesaPaymentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.store = Store.objects.create(
            owner=self.user,
            name='Test Store',
            slug='test-store'
        )
        self.subscription = Subscription.objects.create(
            store=self.store,
            plan='premium',
            status='trialing'
        )

    @patch('storefront.mpesa.MpesaGateway.get_token')
    @patch('storefront.mpesa.MpesaGateway.initiate_stk_push')
    def test_payment_initiation(self, mock_stk_push, mock_get_token):
        """Test payment initiation flow"""
        self.client.login(username='testuser', password='testpass123')
        
        # Mock successful STK push
        mock_get_token.return_value = "test_token"
        mock_stk_push.return_value = {
            'CheckoutRequestID': 'ws_CO_123456789',
            'MerchantRequestID': 'test_merchant_123',
            'ResponseCode': '0',
            'ResponseDescription': 'Success'
        }

        response = self.client.post(
            reverse('storefront:store_upgrade', args=[self.store.slug]),
            {'phone_number': '0712345678'}
        )

        # Verify response
        self.assertEqual(response.status_code, 302)  # Redirects to dashboard
        
        # Verify payment record created
        payment = MpesaPayment.objects.filter(subscription=self.subscription).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(payment.amount, 999)

    @patch('storefront.mpesa.MpesaGateway.get_token')
    @patch('storefront.mpesa.MpesaGateway.initiate_stk_push')
    def test_payment_initiation_failure(self, mock_stk_push, mock_get_token):
        """Test payment initiation failure handling"""
        self.client.login(username='testuser', password='testpass123')
        
        # Mock failed STK push
        mock_get_token.return_value = "test_token"
        mock_stk_push.side_effect = Exception("Failed to initiate payment")

        response = self.client.post(
            reverse('storefront:store_upgrade', args=[self.store.slug]),
            {'phone_number': '0712345678'}
        )

        # Verify response shows error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Failed to initiate payment")

    def test_mpesa_callback_success(self):
        """Test successful M-Pesa callback handling"""
        # Create pending payment
        payment = MpesaPayment.objects.create(
            subscription=self.subscription,
            checkout_request_id='ws_CO_123456789',
            merchant_request_id='test_merchant_123',
            phone_number='254712345678',
            amount=999,
            status='pending'
        )

        # Simulate successful callback
        callback_data = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "test_merchant_123",
                    "CheckoutRequestID": "ws_CO_123456789",
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully."
                }
            }
        }

        response = self.client.post(
            reverse('storefront:mpesa_callback'),
            data=json.dumps(callback_data),
            content_type='application/json'
        )

        # Verify response
        self.assertEqual(response.status_code, 200)
        
        # Refresh payment from db
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'completed')
        
        # Verify subscription activated
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, 'active')
        self.assertIsNotNone(self.subscription.next_billing_date)

    def test_subscription_trial_expiration(self):
        """Test trial expiration handling"""
        # Create subscription with expired trial
        self.subscription.trial_ends_at = timezone.now() - timedelta(days=1)
        self.subscription.save()

        # Create successful payment
        MpesaPayment.objects.create(
            subscription=self.subscription,
            checkout_request_id='ws_CO_123456789',
            merchant_request_id='test_merchant_123',
            phone_number='254712345678',
            amount=999,
            status='completed'
        )

        # Run management command
        from django.core.management import call_command
        call_command('process_subscriptions')

        # Verify subscription converted to active
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, 'active')
        self.assertIsNotNone(self.subscription.next_billing_date)

    def test_subscription_renewal(self):
        """Test subscription renewal process"""
        # Set up active subscription due for renewal
        self.subscription.status = 'active'
        self.subscription.next_billing_date = timezone.now() - timedelta(days=1)
        self.subscription.save()

        # Create previous successful payment
        MpesaPayment.objects.create(
            subscription=self.subscription,
            checkout_request_id='ws_CO_123456789',
            merchant_request_id='test_merchant_123',
            phone_number='254712345678',
            amount=999,
            status='completed'
        )

        # Mock STK push for renewal
        with patch('storefront.mpesa.MpesaGateway.get_token') as mock_get_token:
            with patch('storefront.mpesa.MpesaGateway.initiate_stk_push') as mock_stk_push:
                mock_get_token.return_value = "test_token"
                mock_stk_push.return_value = {
                    'CheckoutRequestID': 'ws_CO_987654321',
                    'MerchantRequestID': 'test_merchant_456',
                    'ResponseCode': '0',
                    'ResponseDescription': 'Success'
                }

                # Run management command
                from django.core.management import call_command
                call_command('process_subscriptions')

        # Verify new payment created
        new_payment = MpesaPayment.objects.filter(
            subscription=self.subscription,
            status='pending'
        ).first()
        self.assertIsNotNone(new_payment)
        self.assertEqual(new_payment.amount, 999)