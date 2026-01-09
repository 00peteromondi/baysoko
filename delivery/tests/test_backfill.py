from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from listings.models import Order
from delivery.models import DeliveryRequest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from listings.models import Order
from delivery.models import DeliveryRequest

User = get_user_model()


class BackfillCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='seller', password='pass')

    def test_backfill_creates_deliveryrequest_for_order(self):
        order = Order.objects.create(user=self.user, total_price=100.00)

        # run management command (should be idempotent if delivery already created)
        call_command('backfill_deliveries')

        # reload order and ensure it references a DeliveryRequest
        order.refresh_from_db()
        self.assertNotEqual(order.delivery_request_id, '')
        # the DeliveryRequest referenced should exist
        dr = DeliveryRequest.objects.filter(id=order.delivery_request_id).first()
        self.assertIsNotNone(dr)