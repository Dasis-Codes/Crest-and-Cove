import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('carts', '0003_cartitem_user_alter_cartitem_cart'),
        ('orders', '0002_orderproduct_variation_optional'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderproduct',
            name='cart_item',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='carts.cartitem',
            ),
        ),
    ]