from django.db import migrations, models
import uuid


def create_third_party_extension(apps, schema_editor):
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;")


def drop_third_party_extension(apps, schema_editor):
    schema_editor.execute("DROP EXTENSION IF EXISTS pg_trgm;DROP EXTENSION IF EXISTS fuzzystrmatch;")


class Migration(migrations.Migration):
    dependencies = [('core', '0001_initial')]

    operations = [
        migrations.RunPython(create_third_party_extension, reverse_code=drop_third_party_extension, atomic=True)
    ]
