from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0041_document_is_read"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="toc_data",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="document",
            name="toc_status",
            field=models.CharField(
                choices=[
                    ("not_started", "Not Started"),
                    ("queued", "Queued"),
                    ("processing", "Processing"),
                    ("succeeded", "Succeeded"),
                    ("failed", "Failed"),
                ],
                default="not_started",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="toc_source",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="document",
            name="toc_error",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="document",
            name="toc_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="document",
            name="toc_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
