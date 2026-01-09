from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from delivery.models import DeliveryRequest
from listings.models import Order
from unittest.mock import patch, Mock

User = get_user_model()


@override_settings(DELIVERY_WEBHOOK_KEY='wk', DELIVERY_SYSTEM_API_KEY='sk', DELIVERY_SYSTEM_URL='http://example.test')
class SyncWebhookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='user1', password='pass')
        self.staff = User.objects.create_user(username='staff', password='pass', is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        # Prevent any external HTTP calls during tests
        self._requests_patcher = patch('requests.post')
        self.mock_requests_post = self._requests_patcher.start()
        self.addCleanup(self._requests_patcher.stop)
        # Default mock response for any external POST
        default_resp = Mock()
        default_resp.status_code = 200
        default_resp.text = 'OK'
        default_resp.json.return_value = {}
        self.mock_requests_post.return_value = default_resp

        # create order and delivery
        self.order = Order.objects.create(user=self.user, total_price=50.0)
        # Some code paths may auto-create a DeliveryRequest for an Order; reuse if present
        existing = DeliveryRequest.objects.filter(order_id=str(self.order.id)).first()
        if existing:
            self.delivery = existing
        else:
            self.delivery = DeliveryRequest.objects.create(
                order_id=str(self.order.id),
                tracking_number='T123',
                status='pending',
            pickup_name='Pickup',
            pickup_address='Addr',
            pickup_phone='0711000000',
            recipient_name='Recipient',
            recipient_address='Addr',
            recipient_phone='0711999999',
            package_description='Items',
            package_weight=1.0,
            delivery_fee=0,
            total_amount=50.0
        )

    def test_webhook_accepts_x_api_key(self):
        url = '/delivery/api/webhook/'
        data = {'tracking_number': self.delivery.tracking_number, 'status': 'delivered'}
        resp = self.client.post(url, data, format='json', HTTP_X_API_KEY='wk')
        self.assertEqual(resp.status_code, 200)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, 'delivered')

    def test_webhook_accepts_bearer_token(self):
        url = '/delivery/api/webhook/'
        data = {'tracking_number': self.delivery.tracking_number, 'status': 'delivered'}
        resp = self.client.post(url, data, format='json', HTTP_AUTHORIZATION='Bearer sk')
        self.assertEqual(resp.status_code, 200)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, 'delivered')

    @patch('requests.post')
    def test_update_status_api_updates_order_and_calls_external(self, mock_post):
        # Mock external POST to return success
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'id': 'external-1'}
        mock_post.return_value = mock_resp

        client = APIClient()
        client.force_authenticate(user=self.staff)
        url = f'/delivery/api/deliveries/{self.delivery.id}/update_status/'
        resp = client.post(url, {'status': 'delivered'}, format='json')
        self.assertEqual(resp.status_code, 200)

        # delivery should be updated
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, 'delivered')

        # order should be updated via integration mapping
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'delivered')

        # external sync should have been called
        self.assertTrue(mock_post.called)
