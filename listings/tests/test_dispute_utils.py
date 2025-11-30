from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

from listings.models import Order, OrderItem, Listing, Category, Escrow
from listings.dispute_utils import DisputeManager
from storefront.models import Store

User = get_user_model()

class DisputeManagerTestCase(TestCase):
    def setUp(self):
        # Create test users
        self.buyer = User.objects.create_user(
            username='testbuyer',
            email='buyer@test.com',
            password='testpass123'
        )
        self.seller = User.objects.create_user(
            username='testseller',
            email='seller@test.com',
            password='testpass123'
        )
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass123'
        )
        
        # Create store
        self.store = Store.objects.create(
            name='Test Store',
            owner=self.seller,
            description='Test store',
            slug='test-store'
        )
        
        # Create category
        self.category = Category.objects.create(
            name='Test Category',
            description='Test category'
        )
        
        # Create listing
        self.listing = Listing.objects.create(
            title='Test Listing',
            description='Test description',
            price=Decimal('100.00'),
            seller=self.seller,
            store=self.store,
            category=self.category
        )
        
        # Create shipped order
        self.order = Order.objects.create(
            user=self.buyer,
            total_price=Decimal('100.00'),
            status='shipped'
        )
        
        # Create order item
        self.order_item = OrderItem.objects.create(
            order=self.order,
            listing=self.listing,
            quantity=1,
            price=self.listing.price,
            shipped=True,
            shipped_at=timezone.now()
        )
        
        # Create escrow
        self.escrow = Escrow.objects.create(
            order=self.order,
            amount=self.order.total_price
        )

    def test_create_dispute(self):
        """Test dispute creation"""
        reason = 'item_not_as_described'
        description = 'The item color is different from the listing'
        
        DisputeManager.create_dispute(
            self.order,
            reason,
            description
        )
        
        # Refresh order from database
        self.order.refresh_from_db()
        self.escrow.refresh_from_db()
        
        # Check status updates
        self.assertEqual(self.order.status, 'disputed')
        self.assertEqual(self.escrow.status, 'disputed')

    def test_invalid_dispute_creation(self):
        """Test invalid dispute creation attempts"""
        # Try to dispute a pending order
        self.order.status = 'pending'
        self.order.save()
        
        with self.assertRaises(ValidationError):
            DisputeManager.create_dispute(
                self.order,
                'item_not_received',
                'Never received the item'
            )
        
        # Try with invalid reason
        self.order.status = 'shipped'
        self.order.save()
        
        with self.assertRaises(ValidationError):
            DisputeManager.create_dispute(
                self.order,
                'invalid_reason',
                'Test description'
            )

    def test_resolve_dispute_with_refund(self):
        """Test dispute resolution with refund"""
        # Create dispute first
        DisputeManager.create_dispute(
            self.order,
            'item_not_as_described',
            'Wrong color received'
        )
        
        # Resolve with full refund
        DisputeManager.resolve_dispute(
            self.order,
            resolution='refund_approved',
            refund_amount=self.order.total_price
        )
        
        # Check status updates
        self.order.refresh_from_db()
        self.escrow.refresh_from_db()
        
        self.assertEqual(self.order.status, 'resolved')
        self.assertEqual(self.escrow.status, 'refunded')
        self.assertIsNotNone(self.escrow.dispute_resolved_at)

    def test_resolve_dispute_with_partial_refund(self):
        """Test dispute resolution with partial refund"""
        # Create dispute
        DisputeManager.create_dispute(
            self.order,
            'item_not_as_described',
            'Minor defect found'
        )
        
        # Resolve with partial refund
        partial_refund = Decimal('30.00')
        DisputeManager.resolve_dispute(
            self.order,
            resolution='partial_refund',
            refund_amount=partial_refund,
            seller_penalty=Decimal('10.00')
        )
        
        # Check status updates
        self.order.refresh_from_db()
        self.escrow.refresh_from_db()
        
        self.assertEqual(self.order.status, 'resolved')
        self.assertEqual(self.escrow.status, 'refunded')

    def test_mediate_dispute(self):
        """Test dispute mediation"""
        # Create dispute
        DisputeManager.create_dispute(
            self.order,
            'item_not_as_described',
            'Item quality issues'
        )
        
        # Add mediation notes
        mediator_notes = {
            'mediator': self.admin,
            'notes': 'Contacted both parties'
        }
        proposed_solution = 'Seller offers 50% refund'
        
        DisputeManager.mediate_dispute(
            self.order,
            mediator_notes,
            proposed_solution
        )
        
        # The order should still be in disputed status
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'disputed')