from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from ..models import Store


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class BundlesAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='owner', email='owner@example.com', password='pass')
        self.staff = User.objects.create_user(username='staff', email='staff@example.com', password='pass')
        self.staff.is_staff = True
        self.staff.save()

        self.store = Store.objects.create(owner=self.owner, name='Test Store', slug='test-store')

    def test_owner_can_access_bundle_dashboard(self):
        self.client.force_login(self.owner)
        url = reverse('storefront:bundle_dashboard', kwargs={'slug': self.store.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_staff_user_can_access_bundle_dashboard(self):
        self.client.force_login(self.staff)
        url = reverse('storefront:bundle_dashboard', kwargs={'slug': self.store.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
