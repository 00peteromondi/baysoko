from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model


class ListingCreatePermissionTests(TestCase):
    def test_anonymous_user_redirects_to_login(self):
        """Anonymous users should be redirected to login with next param."""
        url = reverse('listing-create')
        resp = self.client.get(url)
        # should redirect to login
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('login'), resp['Location'])
        self.assertIn('next=', resp['Location'])

    def test_authenticated_user_gets_listing_create(self):
        """Logged-in users can access the listing create page."""
        User = get_user_model()
        user = User.objects.create_user(username='seller1', password='testpass')
        self.client.login(username='seller1', password='testpass')
        # Ensure the user has a store so the view allows access
        from storefront.models import Store
        Store.objects.create(owner=user, name='Seller1 Store', slug='seller1-store')
        url = reverse('listing-create')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)


class HomePageLinksTests(TestCase):
    def test_homepage_shows_login_next_for_anonymous(self):
        """The home page should link to login with next param for create-listing CTAs when anonymous."""
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)
        # ensure there's a login link that includes next= for the listing-create target
        self.assertIn('?next=', resp.content.decode('utf-8'))
