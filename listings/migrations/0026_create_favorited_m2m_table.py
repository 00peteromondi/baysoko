"""Create the missing `listings_listing_favorited_by` m2m table.

This migration adds a concrete table for the `favorited_by` ManyToManyField.
It intentionally mirrors Django's auto-generated m2m table structure and
is safe to run in development when the SeparateDatabaseAndState migration
(0020) skipped actual database operations.
"""
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0025_category_is_featured_listing_discount_price_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ListingFavoritedBy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('listing', models.ForeignKey(on_delete=models.CASCADE, to='listings.Listing')),
                ('user', models.ForeignKey(on_delete=models.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'listings_listing_favorited_by',
                'managed': True,
                'unique_together': {('listing', 'user')},
            },
        ),
    ]
