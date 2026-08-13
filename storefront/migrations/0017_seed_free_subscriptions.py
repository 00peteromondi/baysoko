from django.db import migrations, models
import django.utils.timezone as timezone


def create_free_subscriptions(apps, schema_editor):
    Store = apps.get_model('storefront', 'Store')
    Subscription = apps.get_model('storefront', 'Subscription')
    now = timezone.now()

    stores = Store.objects.all()
    created = 0
    for store in stores:
        # Skip if store already has any subscriptions
        existing = Subscription.objects.filter(store=store).exists()
        if existing:
            continue

        # Create a zero-amount free subscription row
        Subscription.objects.create(
            store=store,
            plan='free',
            status='active',
            amount=0,
            currency='KES',
            started_at=now,
            metadata={'seeded_free_subscription': True},
        )
        created += 1

    # Optionally log to stdout during migration
    try:
        from django.db import connection
        print(f"Seeded {created} free subscription(s) for existing stores.")
    except Exception:
        pass


def remove_seeded_free_subscriptions(apps, schema_editor):
    Subscription = apps.get_model('storefront', 'Subscription')
    Subscription.objects.filter(metadata__has_key='seeded_free_subscription').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0016_add_free_plan_choice'),
    ]

    operations = [
        migrations.RunPython(create_free_subscriptions, remove_seeded_free_subscriptions),
    ]
