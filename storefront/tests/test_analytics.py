from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from ..models import Store, Subscription
from listings.models import Listing, Category, OrderItem, Order
from reviews.models import Review

User = get_user_model()

class AnalyticsViewsTests(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        # Use test client with enforce_csrf_checks=False for tests
        self.client = Client(enforce_csrf_checks=False)
        # Ensure login succeeds
        login_successful = self.client.login(username='testuser', password='testpass123')
        self.assertTrue(login_successful, "Test user login failed")
        
        # Create a store
        self.store = Store.objects.create(
            name='Test Store',
            slug='test-store',
            owner=self.user,
            description='Test store description',
            is_premium=True
        )
        
        # Create a category
        self.category = Category.objects.create(
            name='Test Category',
            description='Test category description'
        )
        
        # Create some listings
        self.listing1 = Listing.objects.create(
            title='Test Listing 1',
            price=Decimal('100.00'),
            description='Test description',
            seller=self.user,
            store=self.store,
            category=self.category,
            is_active=True
        )
        
        self.listing2 = Listing.objects.create(
            title='Test Listing 2',
            price=Decimal('200.00'),
            description='Test description',
            seller=self.user,
            store=self.store,
            category=self.category,
            is_active=True
        )
        
        # Create orders
        order1 = Order.objects.create(
            user=self.user,
            total_price=self.listing1.price
        )
        OrderItem.objects.create(
            order=order1,
            listing=self.listing1,
            quantity=1,
            price=self.listing1.price,
        )
        
        order2 = Order.objects.create(
            user=self.user,
            total_price=self.listing2.price
        )
        OrderItem.objects.create(
            order=order2,
            listing=self.listing2,
            quantity=1,
            price=self.listing2.price,
        )
        
        # Create a review from the test user
        Review.objects.create(
            reviewer=self.user,
            seller=self.store.owner,
            rating=4,
            comment='Great store and service'
        )
        
        # Create another user and review from them
        other_user = User.objects.create_user(
            username='reviewer2',
            email='reviewer2@example.com',
            password='testpass123'
        )
        Review.objects.create(
            reviewer=other_user,
            seller=self.store.owner,
            rating=5,
            comment='Excellent seller'
        )

    def test_seller_analytics_view(self):
        """Test the seller analytics dashboard view"""
        url = reverse('storefront:seller_analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'storefront/seller_analytics.html')
        
        # Check context data
        self.assertEqual(response.context['total_revenue'], Decimal('300.00'))
        self.assertEqual(response.context['total_orders'], 2)
        self.assertEqual(response.context['active_stores'], 1)
        self.assertEqual(response.context['premium_stores'], 1)
        self.assertEqual(response.context['active_listings'], 2)
        
        # Check that trends are computed
        self.assertTrue('revenue_orders_trend_data' in response.context)
        self.assertTrue('store_performance_data' in response.context)
        self.assertTrue('top_stores' in response.context)
        self.assertTrue('top_categories' in response.context)
        self.assertTrue('recent_activity' in response.context)
        
        # Verify recent activity includes orders and reviews
        recent_activity = response.context['recent_activity']
        self.assertTrue(any(a['type'] == 'Order' for a in recent_activity))
        # Reviews now shown in seller dashboard instead of listing specific

    def test_store_analytics_view(self):
        """Test the individual store analytics view"""
        url = reverse('storefront:store_analytics', kwargs={'slug': self.store.slug})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'storefront/store_analytics.html')
        
        # Check context data
        self.assertEqual(response.context['store'], self.store)
        self.assertEqual(response.context['revenue'], Decimal('300.00'))
        self.assertEqual(response.context['orders_count'], 2)
        self.assertEqual(response.context['active_listings'], 2)
        
        # Verify chart data is present
        self.assertTrue('revenue_trend_data' in response.context)
        self.assertTrue('category_data' in response.context)
        self.assertTrue('demographics_data' in response.context)
        self.assertTrue('locations_data' in response.context)
        
        # Check top products
        top_products = response.context['top_products']
        self.assertEqual(len(top_products), 2)
        self.assertTrue(any(p['revenue'] == Decimal('200.00') for p in top_products))
        
        # Check recent activity includes all types
        recent_activity = response.context['recent_activity']
        activity_types = {a['type'] for a in recent_activity}
        self.assertTrue('Order' in activity_types)
        self.assertTrue('Review' in activity_types)
        self.assertTrue('Listing' in activity_types)

    def test_analytics_period_filtering(self):
        """Test that analytics properly filter by time period"""
        # Test 24h period
        response = self.client.get(
            reverse('storefront:seller_analytics'),
            {'period': '24h'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['period'], '24h')
        
        # Test 7d period
        response = self.client.get(
            reverse('storefront:seller_analytics'),
            {'period': '7d'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['period'], '7d')
        
        # Test 30d period
        response = self.client.get(
            reverse('storefront:seller_analytics'),
            {'period': '30d'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['period'], '30d')
        
        # Test all time (no period)
        response = self.client.get(
            reverse('storefront:seller_analytics'),
            {'period': 'all'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['period'], 'all')

    def test_analytics_requires_login(self):
        """Test that analytics views require authentication"""
        self.client.logout()
        
        # Try seller analytics
        response = self.client.get(reverse('storefront:seller_analytics'))
        self.assertRedirects(
            response,
            f"/users/login/?next={reverse('storefront:seller_analytics')}"
        )
        
        # Try store analytics
        response = self.client.get(
            reverse('storefront:store_analytics', kwargs={'slug': self.store.slug})
        )
        self.assertRedirects(
            response,
            f"/users/login/?next={reverse('storefront:store_analytics', kwargs={'slug': self.store.slug})}"
        )

    def test_store_analytics_owner_only(self):
        """Test that store analytics are only accessible to store owner"""
        # Create another user
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        
        # Login as other user
        self.client.login(username='otheruser', password='otherpass123')
        
        # Try to access store analytics
        response = self.client.get(
            reverse('storefront:store_analytics', kwargs={'slug': self.store.slug})
        )
        self.assertEqual(response.status_code, 404)