from django.db import migrations


def seed_missing_routes(apps, schema_editor):
    DeliveryRouteRate = apps.get_model('delivery', 'DeliveryRouteRate')

    rates = {
        ('kendu', 'oyugis'): 250,
        ('kendu', 'ndhiwa'): 250,
        ('mbita', 'ndhiwa'): 300,
        ('rodi', 'suba'): 350,
        ('rodi', 'ndhiwa'): 250,
        ('oyugis', 'ndhiwa'): 250,
        ('ndhiwa', 'suba'): 300,
        ('kendu', 'mbita'): 300,
    }

    for (origin, destination), fee in rates.items():
        obj, created = DeliveryRouteRate.objects.get_or_create(
            origin=origin,
            destination=destination,
            defaults={'base_fee': fee, 'is_active': True},
        )
        if not created and obj.base_fee != fee:
            obj.base_fee = fee
            obj.is_active = True
            obj.save(update_fields=['base_fee', 'is_active'])

        # Ensure reverse route exists at same fee
        obj_rev, created_rev = DeliveryRouteRate.objects.get_or_create(
            origin=destination,
            destination=origin,
            defaults={'base_fee': fee, 'is_active': True},
        )
        if not created_rev and obj_rev.base_fee != fee:
            obj_rev.base_fee = fee
            obj_rev.is_active = True
            obj_rev.save(update_fields=['base_fee', 'is_active'])


class Migration(migrations.Migration):
    dependencies = [
        ('delivery', '0011_add_kendu_mbita_route_rate'),
    ]

    operations = [
        migrations.RunPython(seed_missing_routes, migrations.RunPython.noop),
    ]
