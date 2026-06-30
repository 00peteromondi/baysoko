from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from types import SimpleNamespace

from ..models import Store, Subscription
from ..models_bulk import BatchJob
from ..forms_bulk import BulkImportForm
from ..tasks_bulk import process_import_task, process_product_import_row
from listings.models import Listing

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

    @patch('storefront.tasks_bulk._send_import_summary_email')
    @patch('notifications.utils.notify_listing_saved')
    def test_import_task_sends_one_summary_email_without_listing_emails(self, mock_notify, mock_summary):
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
