from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_orderproduct_cart_item'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_method',
            field=models.CharField(
                blank=True,
                choices=[
                    ('Safepay', 'Safepay'),
                    ('Cash on Delivery', 'Cash on Delivery'),
                ],
                default='',
                max_length=32,
            ),
        ),
    ]