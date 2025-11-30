from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from ..models import Store, Subscription
from listings.models import Listing, Category
from django.urls import reverse


User = get_user_model()


class StoreCreationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='seller1', email='s1@example.com', password='pass')

    def test_non_pro_cannot_create_second_store_model(self):
        """Model-level validation should prevent creating a second store for non-pro users."""
        first = Store.objects.create(owner=self.user, name='First Store', slug='first-store')
        second = Store(owner=self.user, name='Second Store', slug='second-store')
        with self.assertRaises(ValidationError):
            second.save()

    def test_non_pro_store_create_view_redirects_to_edit(self):
        """View should redirect non-pro users trying to create an additional store to edit their existing store."""
        # create initial store
        Store.objects.create(owner=self.user, name='First Store', slug='first-store')
        self.client.force_login(self.user)
        url = reverse('storefront:store_create')
        resp = self.client.get(url)
        # Should redirect because non-pro users cannot create a second store
        self.assertEqual(resp.status_code, 302)

    def test_listing_create_view_redirects_when_no_store(self):
        """ListingCreateView should redirect users without a store to store_create."""
        self.client.force_login(self.user)
        url = reverse('listing-create')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

    def test_pro_user_with_active_subscription_can_create_second_store(self):
        """If the user has an active subscription, they should be allowed to create additional stores via the view."""
        first = Store.objects.create(owner=self.user, name='First Store', slug='first-store')
        # Create an active subscription tied to first store
        Subscription.objects.create(store=first, plan='premium', status='active')

        self.client.force_login(self.user)
        url = reverse('storefront:store_create')
        data = {
            'name': 'Second Store',
            'slug': 'second-store',
            'description': 'Another shop',
            'is_premium': False,
        }
        resp = self.client.post(url, data, follow=True)
        # After successful creation, should land on seller dashboard
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Store.objects.filter(owner=self.user, slug='second-store').exists())

    def test_listing_create_post_attaches_store(self):
        """Posting to the listing create view when the user has a store should create a listing attached to that store."""
        cat = Category.objects.create(name='General')
        store = Store.objects.create(owner=self.user, name='First Store', slug='first-store')
        self.client.force_login(self.user)
        url = reverse('listing-create')
        data = {
            'title': 'Test Item',
            'description': 'A test listing',
            'price': '100.00',
            'category': str(cat.id),
            'location': 'HB_Town',
            'condition': 'used',
            'delivery_option': 'pickup',
            'stock': '1',
            'store': str(store.id),
        }
        resp = self.client.post(url, data, follow=True)
        # Followed redirect to listing detail or dashboard, should end OK
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Listing.objects.filter(title='Test Item', store=store).exists())

    def test_non_pro_cannot_create_second_store_via_post(self):
        """Attempting to POST a second store as a non-pro user should not create it and should redirect (deny)."""
        Store.objects.create(owner=self.user, name='First Store', slug='first-store')
        self.client.force_login(self.user)
        url = reverse('storefront:store_create')
        data = {
            'name': 'Second Store',
            'slug': 'second-store',
            'description': 'Another shop',
            'is_premium': False,
        }
        resp = self.client.post(url, data, follow=False)
        # Should redirect to edit (302) and not create the second store
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Store.objects.filter(owner=self.user, slug='second-store').exists())
