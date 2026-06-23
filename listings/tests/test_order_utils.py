from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

from listings.models import Order, OrderItem, Listing, Category, Escrow
from listings.order_utils import OrderManager
from storefront.models import Store

User = get_user_model()

class OrderUtilsTestCase(TestCase):
    def setUp(self):
        # Create test users
        self.buyer = User.objects.create_user(
            username='testbuyer',
            email='buyer@test.com',
            password='testpass123'
        )
        self.seller1 = User.objects.create_user(
            username='seller1',
            email='seller1@test.com',
            password='testpass123'
        )
        self.seller2 = User.objects.create_user(
            username='seller2',
            email='seller2@test.com',
            password='testpass123'
        )
        
        # Create stores
        self.store1 = Store.objects.create(
            name='Test Store 1',
            owner=self.seller1,
            description='Test store 1',
            slug='test-store-1'
        )
        self.store2 = Store.objects.create(
            name='Test Store 2',
            owner=self.seller2,
            description='Test store 2',
            slug='test-store-2'
        )
        
        # Create category
        self.category = Category.objects.create(
            name='Test Category',
            description='Test category'
        )
        
        # Create listings
        self.listing1 = Listing.objects.create(
            title='Test Listing 1',
            description='Test description 1',
            price=Decimal('100.00'),
            seller=self.seller1,
            store=self.store1,
            category=self.category,
            stock=5
        )
        self.listing2 = Listing.objects.create(
            title='Test Listing 2',
            description='Test description 2',
            price=Decimal('150.00'),
            seller=self.seller2,
            store=self.store2,
            category=self.category,
            stock=3
        )
        
        # Create order
        self.order = Order.objects.create(
            user=self.buyer,
            total_price=Decimal('250.00')
        )
        
        # Create order items
        self.order_item1 = OrderItem.objects.create(
            order=self.order,
            listing=self.listing1,
            quantity=1,
            price=self.listing1.price
        )
        self.order_item2 = OrderItem.objects.create(
            order=self.order,
            listing=self.listing2,
            quantity=1,
            price=self.listing2.price
        )
        
        # Create escrow
        self.escrow = Escrow.objects.create(
            order=self.order,
            amount=self.order.total_price
        )

    def test_validate_order_status_transition(self):
        """Test order status transition validation"""
        # Test valid transition
        self.order.status = 'pending'
        OrderManager.validate_order_status_transition(self.order, 'paid')
        
        # Test invalid transition
        with self.assertRaises(ValidationError):
            OrderManager.validate_order_status_transition(self.order, 'delivered')

    def test_mark_items_shipped(self):
        """Test marking items as shipped"""
        # Set order to paid status
        self.order.status = 'paid'
        self.order.save()
        
        # Mark seller1's items as shipped
        OrderManager.mark_items_shipped(
            self.order,
            self.seller1,
            tracking_number='TRACK123'
        )
        
        # Check that only seller1's items are marked shipped
        self.order_item1.refresh_from_db()
        self.order_item2.refresh_from_db()
        self.order.refresh_from_db()
        
        self.assertTrue(self.order_item1.shipped)
        self.assertFalse(self.order_item2.shipped)
        self.assertEqual(self.order.status, 'partially_shipped')
        self.assertEqual(self.order_item1.tracking_number, 'TRACK123')

    def test_confirm_delivery(self):
        """Test order delivery confirmation"""
        # Set up order status
        self.order.status = 'shipped'
        self.order.save()
        
        # Confirm delivery
        OrderManager.confirm_delivery(self.order, self.buyer)
        
        # Check status updates
        self.order.refresh_from_db()
        self.escrow.refresh_from_db()
        
        self.assertEqual(self.order.status, 'delivered')
        self.assertEqual(self.escrow.status, 'released')
        self.assertIsNotNone(self.order.delivered_at)

    def test_complete_order_flow(self):
        """Test complete order flow from paid to delivered"""
        # Start with paid order
        self.order.status = 'paid'
        self.order.save()
        
        # First seller ships
        OrderManager.mark_items_shipped(
            self.order,
            self.seller1,
            tracking_number='TRACK123'
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'partially_shipped')
        
        # Second seller ships
        OrderManager.mark_items_shipped(
            self.order,
            self.seller2,
            tracking_number='TRACK456'
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'shipped')
        
        # Buyer confirms delivery
        OrderManager.confirm_delivery(self.order, self.buyer)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'delivered')

    def test_invalid_operations(self):
        """Test invalid operations are properly handled"""
        # Try to mark shipped before payment
        self.order.status = 'pending'
        self.order.save()
        
        with self.assertRaises(ValidationError):
            OrderManager.mark_items_shipped(
                self.order,
                self.seller1,
                tracking_number='TRACK123'
            )
        
        # Try to confirm delivery before shipping
        self.order.status = 'paid'
        self.order.save()
        
        with self.assertRaises(ValidationError):
            OrderManager.confirm_delivery(self.order, self.buyer)
        
        # Try to have wrong user confirm delivery
        self.order.status = 'shipped'
        self.order.save()
        
        with self.assertRaises(ValidationError):
            OrderManager.confirm_delivery(self.order, self.seller1)