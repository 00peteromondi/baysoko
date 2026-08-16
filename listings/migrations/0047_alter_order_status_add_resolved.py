from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0046_order_platform_tax_order_subtotal_order_tax_rate'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending Payment'),
                    ('paid', 'Paid'),
                    ('partially_shipped', 'Partially Shipped'),
                    ('confirmed', 'Confirmed'),
                    ('shipped', 'Shipped'),
                    ('delivered', 'Delivered'),
                    ('cancelled', 'Cancelled'),
                    ('disputed', 'Disputed'),
                    ('resolved', 'Dispute Resolved'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
    ]
