from django.db import migrations


def fix_legacy_variation_columns(apps, schema_editor):
    table_name = 'store_variation'
    with schema_editor.connection.cursor() as cursor:
        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(
                cursor, table_name
            )
        }

    for old_name, new_name in (
        ('color', 'variation_category'),
        ('size', 'variation_value'),
    ):
        if old_name in columns and new_name not in columns:
            schema_editor.execute(
                f'ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name}'
            )
            columns.remove(old_name)
            columns.add(new_name)


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0002_variation'),
    ]

    operations = [
        migrations.RunPython(
            fix_legacy_variation_columns,
            reverse_code=migrations.RunPython.noop,
        ),
    ]