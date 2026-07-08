from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0036_alter_folder_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="ocr_provider",
            field=models.CharField(blank=True, default="paddleocr", max_length=64),
        ),
        migrations.AddField(
            model_name="document",
            name="ocr_status",
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
            name="ocr_error",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="document",
            name="ocr_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="document",
            name="ocr_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
