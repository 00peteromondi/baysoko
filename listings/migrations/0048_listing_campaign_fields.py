from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0047_alter_order_status_add_resolved'),
    ]

    operations = [
        migrations.AddField(
            model_name='listing',
            name='campaign',
            field=models.CharField(
                blank=True,
                choices=[
                    ('backtoschool', 'Back to School Sale'),
                    ('midyear', 'Mid Year Savings'),
                    ('spring', 'Spring Deals'),
                    ('blackfriday', 'Black Friday Blowout'),
                    ('holiday', 'Holiday Specials'),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='listing',
            name='campaign_added_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
