from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch

from ..models import Store, Subscription
from ..models_bulk import BatchJob
from ..forms_bulk import BulkImportForm

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
