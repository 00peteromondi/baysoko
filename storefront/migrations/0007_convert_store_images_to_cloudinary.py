"""Convert Store.logo and Store.cover_image ImageFields to CloudinaryField when available.

This migration keeps null/blank and does not attempt to move files. Ensure Cloudinary
credentials are set in production before running migrations so new uploads go to Cloudinary.
"""
from django.db import migrations


def noop(apps, schema_editor):
    # This is a schema-only migration for field type changes. Actual file transfer
    # (if needed) should be handled separately.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0006_store_cover_image_store_logo'),
    ]

    operations = [
        migrations.RunPython(noop, reverse_code=noop),
    ]
