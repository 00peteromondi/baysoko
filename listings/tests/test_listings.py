from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from listings.models import Category, Listing
from storefront.models import Store

@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'])
class ListingCreatePermissionTests(TestCase):
    def create_verified_user(self, username, password='testpass'):
        User = get_user_model()
        return User.objects.create_user(
            username=username,
            password=password,
            email=f'{username}@example.com',
            phone_number='+254700000000',
            location='Homa Bay Town',
            email_verified=True,
            phone_verified=True,
            is_verified=True,
        )

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
        user = self.create_verified_user('seller1')
        self.client.login(username='seller1', password='testpass')
        # Ensure the user has a store so the view allows access
        Store.objects.create(owner=user, name='Seller1 Store', slug='seller1-store')
        url = reverse('listing-create')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_category_schemas_include_group_fallback(self):
        """The create view should deliver schemas for child categories via their group."""
        user = self.create_verified_user('seller3', password='pass3')
        self.client.login(username='seller3', password='pass3')
        Store.objects.create(owner=user, name='Store3', slug='store3')

        group_key = 'services2'
        parent_schema = {'fields': [{'name': 'foo', 'label': 'Foo', 'required': False, 'type': 'text'}]}
        parent = Category.objects.create(name='ServicesGroup', schema_group=group_key, fields_schema=parent_schema)
        child = Category.objects.create(name='ChildCat', schema_group=group_key)

        url = reverse('listing-create')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        schemas = resp.context.get('category_schemas', {})
        self.assertIn(str(child.id), schemas)
        self.assertEqual(schemas[str(child.id)], parent_schema)

    def test_listing_form_group_schema_fallback(self):
        """A category without its own schema should inherit fields from its group."""
        from listings.forms import ListingForm
        import json

        user = self.create_verified_user('seller2', password='pass')
        # create a store for the user to satisfy store requirement
        store = Store.objects.create(owner=user, name='Store2', slug='store2')

        # define a group key and schema on the parent
        group_key = 'services'
        parent_schema = {'fields': [{'name': 'consultation_length', 'label': 'Length of Consultation', 'required': True, 'type': 'number'}]}
        parent = Category.objects.create(name='Services', schema_group=group_key, fields_schema=parent_schema)
        # child category has no schema but belongs to same group
        child = Category.objects.create(name='Consulting', schema_group=group_key)

        data = {
            'title': 'Test Service',
            'description': 'Offer a service',
            'price': '50.00',
            'category': str(child.id),
            'location': Listing.HOMABAY_LOCATIONS[0][0],
            'condition': Listing.CONDITION_CHOICES[0][0],
            'delivery_option': Listing.DELIVERY_OPTIONS[0][0],
            'stock': '1',
            'store': str(store.id),
            'dynamic_fields': json.dumps({'consultation_length': '30'})
        }
        image = SimpleUploadedFile('listing.jpg', b'filecontent', content_type='image/jpeg')
        form = ListingForm(data=data, files={'image': image}, user=user)
        self.assertTrue(form.is_valid(), msg=form.errors.as_json())
        self.assertEqual(form.cleaned_data['dynamic_fields']['consultation_length'], '30')

    def test_invalid_listing_post_returns_full_context_and_field_errors(self):
        user = self.create_verified_user('seller4', password='pass4')
        self.client.login(username='seller4', password='pass4')
        store = Store.objects.create(owner=user, name='Store4', slug='store4')
        category = Category.objects.create(name='Stationery')

        response = self.client.post(
            reverse('listing-create'),
            data={
                'title': '',
                'description': '',
                'price': '',
                'category': str(category.id),
                'location': Listing.HOMABAY_LOCATIONS[0][0],
                'condition': '',
                'delivery_option': '',
                'stock': '',
                'store': str(store.id),
                'dynamic_fields': '{}',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('form', response.context)
        self.assertIn('categories', response.context)
        self.assertIn('stores', response.context)
        self.assertTrue(response.context['form'].errors)
        self.assertContains(response, 'Please fix the highlighted fields before saving your listing.')
        self.assertContains(response, 'Title')
        self.assertContains(response, 'Description')



class HomePageLinksTests(TestCase):
    def test_homepage_shows_login_next_for_anonymous(self):
        """The home page should link to login with next param for create-listing CTAs when anonymous."""
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)
        # ensure there's a login link that includes next= for the listing-create target
        self.assertIn('?next=', resp.content.decode('utf-8'))
