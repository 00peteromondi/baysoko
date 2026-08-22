from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0027_expand_bulk_job_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='cancel_at_period_end',
            field=models.BooleanField(
                default=False,
                help_text=(
                    "If set, the subscription stays active until current_period_end, "
                    "then the periodic expiration check finalizes the cancellation."
                ),
            ),
        ),
    ]
