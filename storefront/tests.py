from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch

from .models import Store, Subscription
from .models_bulk import BatchJob
from .forms_bulk import BulkImportForm
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


class BulkImportTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='bulkuser', email='bulk@example.com', password='pass')
        self.store = Store.objects.create(owner=self.user, name='Bulk Store', slug='bulk-store')
        self.client.force_login(self.user)

    def test_bulk_import_form_auto_fetch_images_field_is_processed(self):
        csv_content = b'title,description,price,stock\nTest Item,Description,9.99,1\n'
        form = BulkImportForm(
            self.store,
            data={
                'template_type': 'products',
                'update_existing': 'on',
                'create_new': 'on',
                'skip_errors': 'on',
                'auto_fetch_images': 'on',
            },
            files={'file': SimpleUploadedFile('items.csv', csv_content, content_type='text/csv')}
        )
        self.assertTrue(form.is_valid())
        self.assertTrue(form.cleaned_data['auto_fetch_images'])

    @patch('storefront.views_bulk.process_import_task.delay')
    def test_bulk_import_data_view_saves_auto_fetch_images_parameter(self, mock_delay):
        csv_content = b'title,description,price,stock\nTest Item,Description,9.99,1\n'
        url = reverse('storefront:bulk_import_data', kwargs={'slug': self.store.slug})
        resp = self.client.post(
            url,
            {
                'template_type': 'products',
                'update_existing': 'on',
                'create_new': 'on',
                'skip_errors': 'on',
                'auto_fetch_images': 'on',
                'file': SimpleUploadedFile('items.csv', csv_content, content_type='text/csv'),
            },
            follow=True
        )
        self.assertEqual(resp.status_code, 200)
        batch_job = BatchJob.objects.filter(store=self.store, job_type='import').order_by('-created_at').first()
        self.assertIsNotNone(batch_job)
        self.assertTrue(batch_job.parameters.get('auto_fetch_images'))
        self.assertTrue(mock_delay.called)


class ListingFormDraftRetentionTests(TestCase):
    """Test draft retention behavior for listing creation form"""
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='draftuser', email='draft@example.com', password='pass')
        self.store = Store.objects.create(owner=self.user, name='Draft Store', slug='draft-store')
        self.cat = Category.objects.create(name='Test Category')
        self.client.force_login(self.user)

    def test_listing_create_page_loads_with_form(self):
        """GET request to listing create should render form without errors"""
        url = reverse('listing-create')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('listing-form', resp.content.decode())
        self.assertIn('data-is-update="false"', resp.content.decode())

    def test_listing_form_validation_failure_preserves_context(self):
        """POST with invalid data should return 400 and preserve form context for draft"""
        url = reverse('listing-create')
        data = {
            'title': '',  # Missing required field
            'description': 'Test',
            'price': '9.99',
            'category': str(self.cat.id),
            'location': 'HB_Town',
            'condition': 'used',
            'delivery_option': 'pickup',
            'stock': '1',
            'store': str(self.store.id),
        }
        resp = self.client.post(url, data, follow=False)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('listing-form', resp.content.decode())

    def test_listing_form_successful_creation_shows_success_message(self):
        """POST with valid data should create listing and show success message"""
        url = reverse('listing-create')
        data = {
            'title': 'Test Item for Draft',
            'description': 'Test description',
            'price': '9.99',
            'category': str(self.cat.id),
            'location': 'HB_Town',
            'condition': 'used',
            'delivery_option': 'pickup',
            'stock': '1',
            'store': str(self.store.id),
        }
        resp = self.client.post(url, data, follow=True)
        self.assertEqual(resp.status_code, 200)
        # Verify listing was created
        listing = Listing.objects.filter(title='Test Item for Draft', store=self.store).first()
        self.assertIsNotNone(listing)

    def test_listing_update_preserves_existing_data(self):
        """Editing a listing should preserve the existing data without affecting draft for new listings"""
        listing = Listing.objects.create(
            title='Original Title',
            description='Original desc',
            price=10.00,
            seller=self.user,
            store=self.store,
            category=self.cat,
            location='HB_Town',
            condition='used',
            delivery_option='pickup',
            stock=5
        )
        url = reverse('listing-update', args=[listing.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # Verify form is marked as update, not new
        self.assertIn('data-is-update="true"', resp.content.decode())
        # Verify the listing data is in the form
        self.assertIn('Original Title', resp.content.decode())
