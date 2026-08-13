from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

from listings.models import Order, OrderItem, Listing, Category, Escrow
from storefront.models import Store

User = get_user_model()

class OrderViewsTestCase(TestCase):
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
        self.staff_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass123'
        )
        
        # Set up test client
        self.client = Client()
        
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
            total_price=Decimal('250.00'),
            status='paid'
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

    def test_mark_order_shipped(self):
        """Test marking order as shipped"""
        self.client.login(username='seller1', password='testpass123')
        
        response = self.client.post(
            reverse('mark_order_shipped', args=[self.order.id]),
            {'tracking_number': 'TRACK123'}
        )
        
        # Should redirect to seller orders page
        self.assertRedirects(response, reverse('seller_orders'))
        
        # Verify that only seller1's items are marked shipped
        self.order_item1.refresh_from_db()
        self.order_item2.refresh_from_db()
        self.order.refresh_from_db()
        
        self.assertTrue(self.order_item1.shipped)
        self.assertFalse(self.order_item2.shipped)
        self.assertEqual(self.order.status, 'partially_shipped')
        self.assertEqual(self.order_item1.tracking_number, 'TRACK123')

    def test_confirm_delivery(self):
        """Test confirming delivery"""
        self.client.login(username='testbuyer', password='testpass123')
        
        # Set order to shipped
        self.order.status = 'shipped'
        self.order.save()
        
        response = self.client.post(
            reverse('confirm_delivery', args=[self.order.id])
        )
        
        # Should redirect to order detail page
        self.assertRedirects(response, reverse('order_detail', args=[self.order.id]))
        
        # Verify status updates
        self.order.refresh_from_db()
        self.escrow.refresh_from_db()
        
        self.assertEqual(self.order.status, 'delivered')
        self.assertEqual(self.escrow.status, 'released')
        self.assertIsNotNone(self.order.delivered_at)

    def test_create_dispute(self):
        """Test creating a dispute"""
        self.client.login(username='testbuyer', password='testpass123')
        
        # Set order to shipped
        self.order.status = 'shipped'
        self.order.save()
        
        response = self.client.post(
            reverse('create_dispute', args=[self.order.id]),
            {
                'reason': 'item_not_as_described',
                'description': 'Wrong color received'
            }
        )
        
        # Should redirect to order detail page
        self.assertRedirects(response, reverse('order_detail', args=[self.order.id]))
        
        # Verify status updates
        self.order.refresh_from_db()
        self.escrow.refresh_from_db()
        
        self.assertEqual(self.order.status, 'disputed')
        self.assertEqual(self.escrow.status, 'disputed')

    def test_resolve_dispute(self):
        """Test resolving a dispute (staff only)"""
        # First create a dispute
        self.order.status = 'disputed'
        self.escrow.status = 'disputed'
        # Make the admin user a buyer so they can access the order detail
        self.order.user = self.staff_user
        self.order.save()
        self.escrow.save()

        # Login as admin
        self.client.login(username='admin', password='adminpass123')
        
        # Resolve the dispute
        response = self.client.post(
            reverse('resolve_dispute', args=[self.order.id]),
            {
                'resolution': 'refund',
                'refund_amount': '100.00',
                'seller_penalty': '50.00'
            }
        )
        
        # Should redirect to order detail page
        self.assertRedirects(
            response, 
            reverse('order_detail', args=[self.order.id]),
            status_code=302,
            target_status_code=200,
            fetch_redirect_response=True
        )
        
        # Verify status updates
        self.order.refresh_from_db()
        self.escrow.refresh_from_db()
        
        self.assertEqual(self.order.status, 'resolved')
        self.assertIsNotNone(self.escrow.dispute_resolved_at)

    def test_permissions(self):
        """Test view permissions"""
        # Try to mark shipped as wrong seller
        self.client.login(username='seller2', password='testpass123')
        response = self.client.post(
            reverse('mark_order_shipped', args=[self.order.id]),
            {'tracking_number': 'TRACK123'}
        )
        self.order_item1.refresh_from_db()
        self.assertFalse(self.order_item1.shipped)
        
        # Try to confirm delivery as seller
        self.client.login(username='seller1', password='testpass123')
        self.order.status = 'shipped'
        self.order.save()
        response = self.client.post(
            reverse('confirm_delivery', args=[self.order.id])
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'shipped')
        
        # Try to resolve dispute as non-staff
        self.client.login(username='testbuyer', password='testpass123')
        response = self.client.post(
            reverse('resolve_dispute', args=[self.order.id]),
            {'resolution': 'refund'}
        )
        self.assertEqual(response.status_code, 302)  # Should redirect to order detail with error