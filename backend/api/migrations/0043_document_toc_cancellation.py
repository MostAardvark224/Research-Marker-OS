from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("api", "0042_document_table_of_contents")]

    operations = [
        migrations.AlterField(
            model_name="document",
            name="toc_status",
            field=models.CharField(
                choices=[
                    ("not_started", "Not Started"),
                    ("queued", "Queued"),
                    ("processing", "Processing"),
                    ("succeeded", "Succeeded"),
                    ("failed", "Failed"),
                    ("cancelled", "Cancelled"),
                ],
                default="not_started",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="toc_task_id",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
