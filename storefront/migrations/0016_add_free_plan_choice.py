from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0015_selleranalytics_storeanalytics'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='plan',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('free', 'Free - KSh 0/month'),
                    ('basic', 'Basic - KSh 999/month'),
                    ('premium', 'Premium - KSh 1,999/month'),
                    ('enterprise', 'Enterprise - KSh 4,999/month'),
                ],
                default='free',
            ),
        ),
    ]
