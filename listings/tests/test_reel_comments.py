from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from listings.models import Category, Listing, ListingVideo, ListingVideoComment


class ReelCommentsRouteTests(TestCase):
    def setUp(self):
        notification_patch = patch('notifications.utils.notify_listing_saved')
        notification_patch.start()
        self.addCleanup(notification_patch.stop)

        User = get_user_model()
        self.user = User.objects.create_user(
            username='reeluser',
            email='reeluser@example.com',
            password='testpass123',
            phone_number='0711111111',
            email_verified=True,
            phone_verified=True,
        )
        self.seller = User.objects.create_user(
            username='reelseller',
            email='reelseller@example.com',
            password='testpass123',
            phone_number='0722222222',
            email_verified=True,
            phone_verified=True,
        )
        self.category = Category.objects.create(name='Reel Category')
        self.listing = Listing.objects.create(
            title='Reel Listing',
            description='A listing with a reel',
            price=Decimal('1250.00'),
            seller=self.seller,
            category=self.category,
        )
        self.video = ListingVideo.objects.create(listing=self.listing)
        self.url = reverse('reel_comments', args=['listing', self.video.id])

    def test_get_comments_uses_comments_endpoint(self):
        ListingVideoComment.objects.create(
            video=self.video,
            user=self.user,
            comment='Looks good.',
        )

        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['comments'][0]['comment'], 'Looks good.')

    def test_post_comment_creates_comment_and_updates_count(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {'comment': 'Nice reel.'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['comments_count'], 1)
        self.assertEqual(ListingVideoComment.objects.get(video=self.video).comment, 'Nice reel.')
