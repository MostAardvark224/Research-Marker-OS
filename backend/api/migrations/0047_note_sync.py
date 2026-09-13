import uuid

import api.models
from django.db import migrations, models
import django.db.models.deletion


def populate_note_sync_codes(apps, schema_editor):
    Document = apps.get_model("api", "Document")
    for document in Document.objects.filter(note_sync_code="").iterator():
        document.note_sync_code = uuid.uuid4().hex[:10].upper()
        document.save(update_fields=["note_sync_code"])


class Migration(migrations.Migration):
    dependencies = [("api", "0046_standalone_note_folder")]

    operations = [
        migrations.AddField(
            model_name="document",
            name="note_sync_code",
            field=models.CharField(blank=True, db_index=True, default="", max_length=32),
        ),
        migrations.RunPython(populate_note_sync_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="document",
            name="note_sync_code",
            field=models.CharField(
                default=api.models.generate_note_sync_code,
                editable=False,
                max_length=32,
                unique=True,
            ),
        ),
        migrations.CreateModel(
            name="NoteSyncBinding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file_path", models.TextField()),
                ("last_file_hash", models.CharField(blank=True, default="", max_length=64)),
                ("last_app_hash", models.CharField(blank=True, default="", max_length=64)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("document", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="note_sync_binding", to="api.document")),
            ],
        ),
        migrations.CreateModel(
            name="NoteSyncRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content", models.TextField(blank=True, default="")),
                ("reason", models.CharField(blank=True, default="", max_length=64)),
                ("source_file_path", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="note_sync_revisions", to="api.document")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
