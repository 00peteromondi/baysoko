from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from types import SimpleNamespace

from ..models import Store, Subscription
from ..models_bulk import BatchJob
from ..forms_bulk import BulkImportForm
from ..tasks_bulk import _parse_image_candidates, process_import_task, process_product_import_row
from ..image_fetcher import generate_title_image_bytes, save_image_to_listing
from listings.models import Listing, ListingImage

User = get_user_model()


class BulkImportTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='bulkuser', email='bulk@example.com', password='pass')
        self.user.email_verified = True
        self.user.phone_number = '0712345678'
        self.user.save(update_fields=['email_verified', 'phone_number'])
        self.store = Store.objects.create(owner=self.user, name='Bulk Store', slug='bulk-store')
        Subscription.objects.create(store=self.store, plan='premium', status='active')
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

    @patch('storefront.views_bulk._celery_workers_available', return_value=True)
    @patch('storefront.views_bulk.process_import_task.delay')
    def test_bulk_import_data_view_saves_auto_fetch_images_parameter(self, mock_delay, mock_workers):
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

    @patch('storefront.tasks_bulk.fetch_and_attach')
    @patch('notifications.utils.notify_listing_saved')
    def test_product_import_auto_fetches_wikimedia_image_when_missing(self, mock_notify, mock_fetch):
        mock_fetch.return_value = SimpleNamespace(image='listing_images/imported.jpg')

        result = process_product_import_row(
            self.store,
            {
                'title': 'Vintage Camera',
                'description': 'A clean camera',
                'price': '2500',
                'stock': '1',
                'category': 'Photography',
            },
            {
                'update_existing': True,
                'create_new': True,
                'auto_fetch_images': True,
            },
        )

        product = Listing.objects.get(store=self.store, title='Vintage Camera')
        self.assertTrue(product.image)
        self.assertEqual(mock_fetch.call_count, 1)
        self.assertIn('Vintage Camera', mock_fetch.call_args.args[1])
        self.assertEqual(result['status'], 'created')
        self.assertFalse(mock_notify.called)

    @patch('storefront.tasks_bulk.fetch_and_attach')
    def test_product_import_fetches_image_when_no_url_even_if_option_disabled(self, mock_fetch):
        mock_fetch.return_value = SimpleNamespace(image='listing_images/imported.jpg')

        process_product_import_row(
            self.store,
            {
                'title': 'No Url Product',
                'description': 'Needs a fetched image',
                'price': '1500',
                'stock': '1',
            },
            {
                'update_existing': True,
                'create_new': True,
                'auto_fetch_images': False,
            },
        )

        product = Listing.objects.get(store=self.store, title='No Url Product')
        self.assertTrue(product.image)
        self.assertEqual(mock_fetch.call_count, 1)

    def test_parse_image_candidates_ignores_placeholder_hosts(self):
        candidates = _parse_image_candidates({
            'image_url': 'https://picsum.photos/seed/mop/200',
            'image_urls': 'https://example.com/product.jpg,https://placehold.co/300x200',
        })

        self.assertEqual(candidates, ['https://example.com/product.jpg'])

    @patch('storefront.tasks_bulk.fetch_and_attach')
    def test_product_import_fetches_image_when_csv_url_is_placeholder(self, mock_fetch):
        mock_fetch.return_value = SimpleNamespace(image='listing_images/fetched-mop.jpg')

        process_product_import_row(
            self.store,
            {
                'title': 'Mop (1pc)',
                'description': 'Cleaning mop',
                'price': '450',
                'stock': '3',
                'image_url': 'https://picsum.photos/seed/mop/200',
            },
            {
                'update_existing': True,
                'create_new': True,
                'auto_fetch_images': False,
            },
        )

        product = Listing.objects.get(store=self.store, title='Mop (1pc)')
        self.assertTrue(product.image)
        self.assertEqual(mock_fetch.call_count, 1)

    def test_listing_image_url_falls_back_to_first_gallery_image(self):
        listing = Listing.objects.create(
            store=self.store,
            seller=self.user,
            title='Gallery Only Product',
            description='Has only gallery image',
            price='100',
            stock=1,
            condition='used',
            delivery_option='pickup',
            location='HB_Town',
        )
        ListingImage.objects.create(listing=listing, image='listing_images/gallery/gallery-only.jpg')

        self.assertIn('gallery-only', listing.get_image_url())

    def test_listing_fallback_image_endpoint_returns_generated_jpeg(self):
        listing = Listing.objects.create(
            store=self.store,
            seller=self.user,
            title='Generated Fallback Product',
            description='Fallback route image',
            price='100',
            stock=1,
            condition='used',
            delivery_option='pickup',
            location='HB_Town',
        )

        response = self.client.get(reverse('listing_fallback_image', args=[listing.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertGreater(len(response.content), 1000)

    @patch('storefront.tasks_bulk._send_import_summary_email')
    @patch('storefront.tasks_bulk.fetch_and_attach')
    @patch('notifications.utils.notify_listing_saved')
    def test_import_task_sends_one_summary_email_without_listing_emails(self, mock_notify, mock_fetch, mock_summary):
        mock_fetch.return_value = None
        csv_content = b'title,description,price,stock\nBulk One,Description,9.99,1\nBulk Two,Description,12.00,2\n'
        job = BatchJob.objects.create(
            store=self.store,
            job_type='import',
            status='pending',
            created_by=self.user,
            parameters={
                'template_type': 'products',
                'update_existing': True,
                'create_new': True,
                'skip_errors': True,
                'auto_fetch_images': False,
            },
            file=SimpleUploadedFile('items.csv', csv_content, content_type='text/csv'),
        )

        result = process_import_task.apply(args=[job.id], throw=True).get()

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(Listing.objects.filter(store=self.store).count(), 2)
        self.assertFalse(mock_notify.called)
        self.assertEqual(mock_summary.call_count, 1)
        summary = mock_summary.call_args.args[1]
        self.assertEqual(summary['created_count'], 2)
        self.assertEqual(summary['updated_count'], 0)
        self.assertEqual(summary['error_count'], 0)

    @patch('storefront.views_bulk._celery_workers_available', return_value=True)
    @patch('storefront.views_bulk.process_import_task.delay')
    def test_retry_failed_import_items_creates_retry_job(self, mock_delay, mock_workers):
        original = BatchJob.objects.create(
            store=self.store,
            job_type='import',
            status='completed_with_errors',
            created_by=self.user,
            parameters={
                'template_type': 'products',
                'update_existing': True,
                'create_new': True,
                'field_mapping': {'title': 'title', 'price': 'price'},
            },
            errors=[
                {
                    'row': 2,
                    'error': 'Product title is required',
                    'data': {'title': 'Retry Product', 'price': '25'},
                }
            ],
        )

        url = reverse('storefront:retry_failed_import_items', kwargs={'slug': self.store.slug, 'job_id': original.id})
        response = self.client.post(url)

        retry_job = BatchJob.objects.filter(parameters__retry_of_job_id=original.id).first()
        self.assertIsNotNone(retry_job)
        self.assertRedirects(
            response,
            reverse('storefront:bulk_job_detail', kwargs={'slug': self.store.slug, 'job_id': retry_job.id}),
            fetch_redirect_response=False,
        )
        self.assertEqual(retry_job.total_items, 1)
        self.assertEqual(len(retry_job.parameters['retry_rows']), 1)
        self.assertTrue(retry_job.parameters['auto_fetch_images'])
        self.assertTrue(mock_delay.called)

    def test_save_image_to_listing_handles_none_field_proxy(self):
        listing = Listing(
            store=self.store,
            seller=self.user,
            title='Storage Fallback Product',
            description='Fallback image save test',
            price='100',
            stock=1,
            condition='used',
            delivery_option='pickup',
            location='HB_Town',
        )
        listing._suppress_listing_notifications = True
        listing.save()

        with patch('storefront.image_fetcher.getattr', create=True) as mock_getattr:
            import builtins

            def side_effect(obj, name, default=None):
                if name == 'image':
                    return None
                return builtins.getattr(obj, name, default)

            mock_getattr.side_effect = side_effect
            listing_image = save_image_to_listing(
                listing,
                generate_title_image_bytes('Storage Fallback Product'),
                filename='storage-fallback-product.jpg',
            )

        self.assertIsNotNone(listing_image)
        self.assertTrue(str(listing_image.image))
