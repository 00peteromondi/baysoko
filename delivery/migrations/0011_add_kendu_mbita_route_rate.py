from django.db import migrations


def seed_kendu_mbita_rate(apps, schema_editor):
    DeliveryRouteRate = apps.get_model('delivery', 'DeliveryRouteRate')
    DeliveryRouteRate.objects.get_or_create(
        origin='kendu',
        destination='mbita',
        defaults={'base_fee': 300, 'is_active': True},
    )


class Migration(migrations.Migration):
    dependencies = [
        ('delivery', '0010_merge_20260313_1740'),
    ]

    operations = [
        migrations.RunPython(seed_kendu_mbita_rate, migrations.RunPython.noop),
    ]
