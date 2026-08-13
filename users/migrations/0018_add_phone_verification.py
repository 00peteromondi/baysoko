from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0017_accountdeletionlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='phone_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='user',
            name='phone_verification_code',
            field=models.CharField(max_length=7, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='user',
            name='phone_verification_sent_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
