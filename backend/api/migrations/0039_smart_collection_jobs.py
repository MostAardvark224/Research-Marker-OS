import uuid

from django.db import migrations, models
import django.db.models.deletion


def backfill_embedding_metadata(apps, schema_editor):
    Annotation = apps.get_model("api", "Annotations")
    for annotation in Annotation.objects.exclude(embedding_binary__isnull=True).iterator():
        byte_count = len(annotation.embedding_binary or b"")
        annotation.embedding_provider = "gemini"
        annotation.embedding_model = "text-embedding-004"
        annotation.embedding_dimensions = byte_count // 4 if byte_count % 4 == 0 else 0
        annotation.embedding_version = 1
        annotation.save(
            update_fields=[
                "embedding_provider",
                "embedding_model",
                "embedding_dimensions",
                "embedding_version",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0038_paper_context_and_codex"),
    ]

    operations = [
        migrations.AddField(
            model_name="annotations",
            name="embedding_dimensions",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="annotations",
            name="embedding_model",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="annotations",
            name="embedding_provider",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="annotations",
            name="embedding_version",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="SmartCollectionJob",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("task_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="queued",
                        max_length=16,
                    ),
                ),
                ("stage", models.CharField(default="queued", max_length=32)),
                ("progress", models.PositiveSmallIntegerField(default=0)),
                ("embedding_provider", models.CharField(max_length=32)),
                ("embedding_model", models.CharField(max_length=128)),
                ("embedding_dimensions", models.PositiveIntegerField(default=512)),
                ("generation_provider", models.CharField(max_length=32)),
                ("generation_model", models.CharField(max_length=128)),
                ("total_items", models.PositiveIntegerField(default=0)),
                ("processed_items", models.PositiveIntegerField(default=0)),
                ("warnings", models.JSONField(blank=True, default=list)),
                ("error_code", models.CharField(blank=True, default="", max_length=64)),
                ("error_message", models.TextField(blank=True, default="")),
                ("cancel_requested", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["status", "created_at"],
                        name="api_smartco_status_375e38_idx",
                    )
                ],
            },
        ),
        migrations.AddField(
            model_name="smartcollections",
            name="source_job",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="published_collections",
                to="api.smartcollectionjob",
            ),
        ),
        migrations.RunPython(backfill_embedding_metadata, migrations.RunPython.noop),
    ]
