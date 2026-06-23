from django.db import migrations

def fix_changed_by_null(apps, schema_editor):
    DeliveryStatusHistory = apps.get_model('delivery', 'DeliveryStatusHistory')
    
    # Find all records with null changed_by
    null_records = DeliveryStatusHistory.objects.filter(changed_by__isnull=True)
    
    # Get system user (or create one if needed) using historical model
    # The project swaps auth.User with users.User, so load via apps
    User = apps.get_model('users', 'User')
    system_user = User.objects.filter(username='system').first()

    if not system_user:
        # Create a system user if it doesn't exist using the historical model
        system_user = User.objects.create(
            username='system',
            first_name='System',
            last_name='User',
            is_active=False,
            is_staff=False,
            is_superuser=False
        )
        try:
            # Some custom user models may not have set_unusable_password on the instance
            system_user.set_unusable_password()
        except Exception:
            pass
        system_user.save()
    
    # Update null records
    null_records.update(changed_by=system_user)

def reverse_fix(apps, schema_editor):
    # Optional: revert if needed
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('delivery', '0002_ecommerceplatform_integrationconfig_ordersynclog_and_more'),  # Replace with actual previous migration
    ]
    
    operations = [
        migrations.RunPython(fix_changed_by_null, reverse_fix),
    ]