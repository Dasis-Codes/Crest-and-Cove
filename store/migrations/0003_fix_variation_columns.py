from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0002_variation'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                'ALTER TABLE store_variation '
                'RENAME COLUMN color TO variation_category'
            ),
            reverse_sql=(
                'ALTER TABLE store_variation '
                'RENAME COLUMN variation_category TO color'
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE store_variation '
                'RENAME COLUMN size TO variation_value'
            ),
            reverse_sql=(
                'ALTER TABLE store_variation '
                'RENAME COLUMN variation_value TO size'
            ),
        ),
    ]