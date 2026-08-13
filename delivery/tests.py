"""
Tests for delivery app
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from .models import DeliveryRequest, DeliveryPerson, DeliveryService
from .utils import calculate_delivery_fee, calculate_distance


class DeliveryModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.delivery_service = DeliveryService.objects.create(
            name='Test Service',
            service_type='standard',
            base_price=Decimal('50.00'),
            price_per_kg=Decimal('10.00')
        )
    
    def test_delivery_creation(self):
        """Test creating a delivery request"""
        delivery = DeliveryRequest.objects.create(
            order_id='TEST123',
            tracking_number='DLV20231231120000',
            status='pending',
            pickup_name='Test Store',
            pickup_address='123 Test St',
            pickup_phone='+254700000000',
            recipient_name='Test Customer',
            recipient_address='456 Customer St',
            recipient_phone='+254711111111',
            package_description='Test Package',
            package_weight=Decimal('2.5'),
            delivery_fee=Decimal('100.00'),
            total_amount=Decimal('100.00')
        )
        
        self.assertEqual(delivery.status, 'pending')
        self.assertEqual(delivery.order_id, 'TEST123')
    
    def test_status_update(self):
        """Test updating delivery status"""
        delivery = DeliveryRequest.objects.create(
            order_id='TEST456',
            tracking_number='DLV20231231120001',
            status='pending',
            pickup_name='Test Store',
            pickup_address='123 Test St',
            pickup_phone='+254700000000',
            recipient_name='Test Customer',
            recipient_address='456 Customer St',
            recipient_phone='+254711111111',
            package_description='Test Package',
            package_weight=Decimal('2.5'),
            delivery_fee=Decimal('100.00'),
            total_amount=Decimal('100.00')
        )
        
        delivery.update_status('accepted', 'Accepted by system')
        
        self.assertEqual(delivery.status, 'accepted')
        self.assertEqual(delivery.status_history.count(), 1)
    
    def test_calculate_delivery_fee(self):
        """Test delivery fee calculation"""
        fee = calculate_delivery_fee(
            weight=Decimal('5.0'),
            service_type=self.delivery_service
        )
        
        # 50 base + (10 * 5) weight = 100
        self.assertEqual(fee, Decimal('100.00'))
    
    def test_distance_calculation(self):
        """Test distance calculation between coordinates"""
        # Coordinates for two points in Homabay
        distance = calculate_distance(
            -0.5167, 34.4500,  # Point A
            -0.5200, 34.4600   # Point B (~1.2km away)
        )
        
        self.assertGreater(distance, 1.0)
        self.assertLess(distance, 2.0)


class DeliveryIntegrationTests(TestCase):
    def test_create_delivery_from_order(self):
        """Test creating delivery from e-commerce order"""
        from listings.models import Order
        from .integration import create_delivery_from_order
        
        # Create test order
        order = Order.objects.create(
            first_name='Test',
            last_name='Customer',
            email='test@example.com',
            phone_number='+254711111111',
            shipping_address='456 Customer St',
            total_price=Decimal('500.00')
        )
        
        delivery = create_delivery_from_order(order)
        
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.order_id, str(order.id))
        self.assertEqual(delivery.recipient_name, 'Test Customer')
        self.assertEqual(delivery.recipient_phone, '+254711111111')